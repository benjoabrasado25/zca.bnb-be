"""
Airbnb Sync Service - Syncs listings from Airbnb via APIFY.

Uses the tri_angle~airbnb-rooms-urls-scraper actor to fetch
comprehensive listing data from Airbnb URLs.
"""

import logging
import re
import time
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from io import BytesIO

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from listings.models import Listing, ListingImage, ListingAmenity, ListingAmenityMapping, City
from users.models import User
from .models import AirbnbSyncJob

logger = logging.getLogger(__name__)


class AirbnbSyncService:
    """Service for syncing Airbnb listings via APIFY."""

    BASE_URL = 'https://api.apify.com/v2'
    ACTOR_ID = 'tri_angle~airbnb-rooms-urls-scraper'
    REVIEWS_ACTOR_ID = 'tri_angle~airbnb-reviews-scraper'
    TIMEOUT = 30
    POLL_INTERVAL = 10  # seconds
    MAX_IMAGES = 20

    @classmethod
    def get_api_token(cls) -> Optional[str]:
        """Get APIFY API token from settings."""
        return getattr(settings, 'APIFY_TOKEN', None) or None

    @classmethod
    def clean_airbnb_url(cls, url: str) -> str:
        """Clean Airbnb URL - remove query parameters."""
        url = url.strip()
        if '?' in url:
            url = url.split('?')[0]
        return url

    @classmethod
    def extract_airbnb_id(cls, url: str) -> Optional[str]:
        """Extract Airbnb listing ID from URL."""
        match = re.search(r'/rooms/(?:plus/)?(\d+)', url)
        if match:
            return match.group(1)
        return None

    @classmethod
    def start_sync(cls, urls: List[str], host: User) -> Tuple[Optional[str], Optional[str]]:
        """
        Start an APIFY sync job for the given Airbnb URLs.

        Args:
            urls: List of Airbnb listing URLs
            host: User who will own the created listings

        Returns:
            Tuple of (run_id, error_message)
        """
        token = cls.get_api_token()
        if not token:
            return None, "APIFY_TOKEN is not configured. Add it to your environment variables."

        # Clean URLs
        cleaned_urls = [cls.clean_airbnb_url(url) for url in urls if 'airbnb.com' in url]
        if not cleaned_urls:
            return None, "No valid Airbnb URLs provided."

        # Prepare input for APIFY
        start_urls = [{'url': url} for url in cleaned_urls]
        input_data = {
            'startUrls': start_urls,
            'maxListings': len(cleaned_urls),
            'includeReviews': True,
            'maxReviews': 10,
            'proxyConfiguration': {'useApifyProxy': True},
        }

        try:
            response = requests.post(
                f"{cls.BASE_URL}/acts/{cls.ACTOR_ID}/runs",
                params={'token': token},
                json=input_data,
                timeout=cls.TIMEOUT,
            )

            if response.status_code == 401:
                return None, "Invalid APIFY API token."
            elif response.status_code == 404:
                return None, "APIFY actor not found."

            response.raise_for_status()
            data = response.json()

            run_id = data.get('data', {}).get('id')
            if not run_id:
                return None, "No run ID returned from APIFY."

            # Create job record
            AirbnbSyncJob.objects.create(
                run_id=run_id,
                airbnb_urls=cleaned_urls,
                status=AirbnbSyncJob.Status.RUNNING,
            )

            logger.info(f"Started Airbnb sync job {run_id} for {len(cleaned_urls)} URLs")
            return run_id, None

        except requests.RequestException as e:
            error = f"Failed to start sync: {str(e)}"
            logger.error(error)
            return None, error

    @classmethod
    def check_status(cls, run_id: str) -> Tuple[str, Optional[str]]:
        """
        Check the status of an APIFY job.

        Returns:
            Tuple of (status, error_message)
        """
        token = cls.get_api_token()
        if not token:
            return 'FAILED', "APIFY token not configured"

        try:
            response = requests.get(
                f"{cls.BASE_URL}/actor-runs/{run_id}",
                params={'token': token},
                timeout=cls.TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            status = data.get('data', {}).get('status', 'UNKNOWN')
            return status, None

        except requests.RequestException as e:
            return 'FAILED', str(e)

    @classmethod
    def get_results(cls, run_id: str) -> Tuple[List[Dict], Optional[str]]:
        """Get results from a completed APIFY job."""
        token = cls.get_api_token()
        if not token:
            return [], "APIFY token not configured"

        try:
            response = requests.get(
                f"{cls.BASE_URL}/actor-runs/{run_id}/dataset/items",
                params={'token': token},
                timeout=60,
            )
            response.raise_for_status()
            results = response.json()

            logger.info(f"Retrieved {len(results)} results from job {run_id}")
            return results, None

        except requests.RequestException as e:
            return [], str(e)

    @classmethod
    def process_and_create_listing(cls, data: Dict, host: User) -> Tuple[Optional[Listing], str]:
        """
        Process APIFY data and create/update a listing.

        Args:
            data: Raw listing data from APIFY
            host: User to assign as host

        Returns:
            Tuple of (listing, status) where status is 'created', 'updated', or 'error: <message>'
        """
        try:
            # Extract Airbnb ID
            airbnb_id = str(data.get('id', ''))
            if not airbnb_id:
                url = data.get('url', '')
                airbnb_id = cls.extract_airbnb_id(url) or ''

            if not airbnb_id:
                return None, 'error: No Airbnb ID found'

            # Check if listing exists
            listing, created = Listing.objects.get_or_create(
                airbnb_id=airbnb_id,
                defaults={
                    'host': host,
                    'title': data.get('name') or 'Untitled',
                    'description': '',
                    'price_per_night': 0,
                    'address': 'Address pending',
                }
            )

            # Update all fields
            cls._update_basic_info(listing, data)
            cls._update_location(listing, data)
            cls._update_pricing(listing, data)
            cls._update_capacity(listing, data)
            cls._update_ratings(listing, data)
            cls._update_house_rules(listing, data)
            cls._update_highlights(listing, data)

            # Set status to active
            listing.status = Listing.Status.ACTIVE
            listing.last_synced = timezone.now()
            listing.save()

            # Process amenities
            cls._process_amenities(listing, data.get('amenities', []))

            # Process images
            images = data.get('images', [])
            if images:
                cls._process_images(listing, images)

            status = 'created' if created else 'updated'
            logger.info(f"Processed listing {airbnb_id}: {status}")
            return listing, status

        except Exception as e:
            logger.error(f"Error processing listing: {e}", exc_info=True)
            return None, f'error: {str(e)}'

    @classmethod
    def _update_basic_info(cls, listing: Listing, data: Dict):
        """Update basic listing info."""
        listing.title = data.get('name') or data.get('title') or listing.title
        listing.airbnb_url = data.get('url', '') or listing.airbnb_url

        # Description - try multiple fields
        description = data.get('description', '')
        if not description:
            html_desc = data.get('htmlDescription', {})
            if isinstance(html_desc, dict):
                description = html_desc.get('htmlText', '')
        listing.description = description or listing.description

        # Property type
        room_type = (data.get('roomType') or data.get('propertyType') or '').lower()
        if 'entire' in room_type:
            listing.property_type = Listing.PropertyType.ENTIRE_PLACE
        elif 'private' in room_type:
            listing.property_type = Listing.PropertyType.PRIVATE_ROOM
        elif 'shared' in room_type:
            listing.property_type = Listing.PropertyType.SHARED_ROOM

    @classmethod
    def _update_location(cls, listing: Listing, data: Dict):
        """Update location fields."""
        # Coordinates
        coords = data.get('coordinates', {})
        if coords:
            if coords.get('latitude'):
                listing.latitude = Decimal(str(coords['latitude']))
            if coords.get('longitude'):
                listing.longitude = Decimal(str(coords['longitude']))

        # Location text
        location = data.get('location', '')
        location_subtitle = data.get('locationSubtitle', '')
        listing.neighborhood = location or listing.neighborhood
        listing.address = location_subtitle or location or listing.address

        # Parse city from location
        if location_subtitle:
            parts = location_subtitle.split(',')
            if parts:
                city_name = parts[0].strip()
                # Clean city name - remove "City of" prefix (e.g., "City of Taguig" -> "Taguig")
                city_name = re.sub(r'^City of\s+', '', city_name, flags=re.IGNORECASE)
                province = parts[1].strip() if len(parts) > 1 else ''
                city, _ = City.objects.get_or_create(
                    name=city_name,
                    defaults={'province': province, 'country': 'Philippines'}
                )
                listing.city = city

    @classmethod
    def _update_pricing(cls, listing: Listing, data: Dict):
        """Update pricing fields."""
        price_data = data.get('price', {})
        if isinstance(price_data, dict):
            rate = price_data.get('rate')
            if rate:
                listing.price_per_night = Decimal(str(rate))
        elif isinstance(price_data, (int, float)):
            listing.price_per_night = Decimal(str(price_data))

    @classmethod
    def _update_capacity(cls, listing: Listing, data: Dict):
        """Update capacity fields (guests, bedrooms, beds, bathrooms)."""
        if data.get('personCapacity'):
            listing.max_guests = int(data['personCapacity'])

        # Parse from subDescription
        sub_desc = data.get('subDescription', {})
        if isinstance(sub_desc, dict):
            items = sub_desc.get('items', [])
            for item in items:
                item_str = str(item).lower()
                match = re.search(r'(\d+\.?\d*)', item_str)
                if match:
                    num = match.group(1)
                    if 'bedroom' in item_str:
                        listing.bedrooms = int(num)
                    elif 'bed' in item_str and 'bedroom' not in item_str:
                        listing.beds = int(num)
                    elif 'bath' in item_str:
                        listing.bathrooms = Decimal(num)
                    elif 'guest' in item_str:
                        listing.max_guests = int(num)

    @classmethod
    def _update_ratings(cls, listing: Listing, data: Dict):
        """Update rating fields."""
        rating_data = data.get('rating', {})
        if isinstance(rating_data, dict):
            if rating_data.get('guestSatisfaction'):
                listing.rating = Decimal(str(rating_data['guestSatisfaction']))
            if rating_data.get('reviewsCount'):
                listing.reviews_count = int(rating_data['reviewsCount'])
            if rating_data.get('accuracy'):
                listing.rating_accuracy = Decimal(str(rating_data['accuracy']))
            if rating_data.get('cleanliness'):
                listing.rating_cleanliness = Decimal(str(rating_data['cleanliness']))
            if rating_data.get('checkin'):
                listing.rating_checkin = Decimal(str(rating_data['checkin']))
            if rating_data.get('communication'):
                listing.rating_communication = Decimal(str(rating_data['communication']))
            if rating_data.get('location'):
                listing.rating_location = Decimal(str(rating_data['location']))
            if rating_data.get('value'):
                listing.rating_value = Decimal(str(rating_data['value']))

        # Store reviews JSON
        reviews = data.get('reviews', [])
        if reviews:
            listing.reviews = reviews[:20]

    @classmethod
    def _update_house_rules(cls, listing: Listing, data: Dict):
        """Update house rules fields."""
        house_rules = data.get('houseRules', {})
        if not isinstance(house_rules, dict):
            return

        general = house_rules.get('general', [])
        for section in general:
            if not isinstance(section, dict):
                continue

            values = section.get('values', [])
            for rule in values:
                if not isinstance(rule, dict):
                    continue

                title = (rule.get('title') or '').lower()

                # Check-in time
                if 'check-in' in title and 'after' in title:
                    match = re.search(r'(\d{1,2})\s*(am|pm)', title, re.I)
                    if match:
                        hour = int(match.group(1))
                        if match.group(2).lower() == 'pm' and hour != 12:
                            hour += 12
                        listing.check_in_time = f"{hour:02d}:00"

                # Check-out time
                elif 'checkout' in title or 'check-out' in title:
                    match = re.search(r'(\d{1,2})\s*(am|pm)', title, re.I)
                    if match:
                        hour = int(match.group(1))
                        if match.group(2).lower() == 'pm' and hour != 12:
                            hour += 12
                        listing.check_out_time = f"{hour:02d}:00"

                # Self check-in
                elif 'self check-in' in title:
                    listing.self_checkin = True
                    if rule.get('additionalInfo'):
                        listing.checkin_method = rule['additionalInfo']

                # Max guests
                elif 'guest' in title:
                    match = re.search(r'(\d+)', title)
                    if match:
                        listing.max_guests = int(match.group(1))

    @classmethod
    def _update_highlights(cls, listing: Listing, data: Dict):
        """Update highlights."""
        highlights = data.get('highlights', [])
        if highlights:
            listing.highlights = highlights

    @classmethod
    def _process_amenities(cls, listing: Listing, amenities_data: List):
        """Process and link amenities."""
        if not amenities_data:
            return

        # Clear existing
        ListingAmenityMapping.objects.filter(listing=listing).delete()

        for category_data in amenities_data:
            if not isinstance(category_data, dict):
                continue

            category_name = category_data.get('title', 'Features')
            values = category_data.get('values', [])

            # Map category
            category_lower = category_name.lower()
            if 'essential' in category_lower or 'basic' in category_lower:
                category = ListingAmenity.AmenityCategory.ESSENTIALS
            elif 'safety' in category_lower:
                category = ListingAmenity.AmenityCategory.SAFETY
            elif 'location' in category_lower:
                category = ListingAmenity.AmenityCategory.LOCATION
            else:
                category = ListingAmenity.AmenityCategory.FEATURES

            for amenity_item in values:
                if not isinstance(amenity_item, dict):
                    continue

                name = amenity_item.get('title', '')
                available = amenity_item.get('available', True)

                if not name or not available:
                    continue

                amenity, _ = ListingAmenity.objects.get_or_create(
                    name=name,
                    defaults={'category': category}
                )

                ListingAmenityMapping.objects.get_or_create(
                    listing=listing,
                    amenity=amenity,
                )

    @classmethod
    def _process_images(cls, listing: Listing, images_data: List):
        """Download and store listing images."""
        if not images_data:
            return

        # Clear existing images for re-sync
        if listing.images.exists():
            listing.images.all().delete()

        for i, image_data in enumerate(images_data[:cls.MAX_IMAGES]):
            if not isinstance(image_data, dict):
                continue

            image_url = image_data.get('imageUrl') or image_data.get('url')
            if not image_url:
                continue

            caption = image_data.get('caption', '')

            try:
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()

                # Get file extension
                content_type = response.headers.get('content-type', 'image/jpeg')
                ext = 'jpg'
                if 'png' in content_type:
                    ext = 'png'
                elif 'webp' in content_type:
                    ext = 'webp'

                filename = f"listing_{listing.id}_{listing.airbnb_id}_{i}.{ext}"

                listing_image = ListingImage(
                    listing=listing,
                    caption=caption,
                    is_primary=(i == 0),
                    order=i,
                )
                listing_image.image.save(filename, ContentFile(response.content), save=True)

                # Small delay to be nice to servers
                time.sleep(0.2)

            except Exception as e:
                logger.warning(f"Failed to download image {image_url}: {e}")
                continue

    @classmethod
    def sync_and_wait(cls, urls: List[str], host: User, timeout: int = 300) -> Dict:
        """
        Start sync, wait for completion, and process results.

        This is a synchronous method that blocks until complete.
        For async processing, use start_sync() and process_job() separately.
        """
        results = {
            'success': False,
            'run_id': None,
            'created': 0,
            'updated': 0,
            'errors': [],
            'listings': [],
        }

        # Start job
        run_id, error = cls.start_sync(urls, host)
        if error:
            results['errors'].append(error)
            return results

        results['run_id'] = run_id

        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < timeout:
            status, error = cls.check_status(run_id)

            if error:
                results['errors'].append(error)
                break

            if status == 'SUCCEEDED':
                # Get and process results
                listings_data, error = cls.get_results(run_id)
                if error:
                    results['errors'].append(error)
                    break

                for data in listings_data:
                    listing, status = cls.process_and_create_listing(data, host)
                    if listing:
                        results['listings'].append(listing.id)
                        if status == 'created':
                            results['created'] += 1
                        elif status == 'updated':
                            results['updated'] += 1
                    elif status.startswith('error:'):
                        results['errors'].append(status)

                # Update job record
                job = AirbnbSyncJob.objects.filter(run_id=run_id).first()
                if job:
                    job.status = AirbnbSyncJob.Status.SUCCEEDED
                    job.listings_created = results['created']
                    job.listings_updated = results['updated']
                    job.completed_at = timezone.now()
                    job.save()

                results['success'] = True
                break

            elif status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                error_msg = f"Sync job {status}"
                results['errors'].append(error_msg)

                job = AirbnbSyncJob.objects.filter(run_id=run_id).first()
                if job:
                    job.status = AirbnbSyncJob.Status.FAILED
                    job.error_message = error_msg
                    job.completed_at = timezone.now()
                    job.save()
                break

            time.sleep(cls.POLL_INTERVAL)

        return results


# Backwards compatibility alias
ApifyService = AirbnbSyncService
