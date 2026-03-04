"""
APIFY service for syncing Airbnb listings.

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


class ApifyService:
    """Service for syncing Airbnb listings via APIFY."""

    BASE_URL = 'https://api.apify.com/v2'
    ACTOR_ID = 'tri_angle~airbnb-rooms-urls-scraper'
    REVIEWS_ACTOR_ID = 'tri_angle~airbnb-reviews-scraper'
    TIMEOUT = 30
    POLL_INTERVAL = 5  # seconds

    @classmethod
    def get_api_token(cls) -> Optional[str]:
        """Get APIFY API token from settings."""
        return getattr(settings, 'APIFY_TOKEN', None)

    @classmethod
    def extract_airbnb_id(cls, url: str) -> Optional[str]:
        """Extract Airbnb listing ID from URL."""
        # Match patterns like /rooms/12345678 or /rooms/plus/12345678
        match = re.search(r'/rooms/(?:plus/)?(\d+)', url)
        if match:
            return match.group(1)
        return None

    @classmethod
    def start_sync_job(cls, urls: List[str], get_reviews: bool = True, max_reviews: int = 20) -> Tuple[Optional[str], Optional[str]]:
        """
        Start an APIFY actor run to scrape Airbnb listings.

        Args:
            urls: List of Airbnb listing URLs
            get_reviews: Whether to include reviews
            max_reviews: Maximum reviews per listing

        Returns:
            Tuple of (run_id, error_message)
        """
        token = cls.get_api_token()
        if not token:
            return None, "APIFY token not configured"

        # Prepare input
        start_urls = [{'url': url} for url in urls]
        input_data = {
            'startUrls': start_urls,
            'getReviews': get_reviews,
            'maxReviews': max_reviews,
            'proxyConfiguration': {'useApifyProxy': True},
        }

        try:
            response = requests.post(
                f"{cls.BASE_URL}/acts/{cls.ACTOR_ID}/runs",
                params={'token': token},
                json=input_data,
                timeout=cls.TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            run_id = data.get('data', {}).get('id')
            if not run_id:
                return None, "No run ID in response"

            # Create job record
            AirbnbSyncJob.objects.create(
                run_id=run_id,
                airbnb_urls=urls,
                status=AirbnbSyncJob.Status.RUNNING,
            )

            logger.info(f"Started APIFY job {run_id} for {len(urls)} URLs")
            return run_id, None

        except requests.RequestException as e:
            error = f"Failed to start APIFY job: {str(e)}"
            logger.error(error)
            return None, error

    @classmethod
    def check_job_status(cls, run_id: str) -> Tuple[str, Optional[str]]:
        """
        Check the status of an APIFY job.

        Returns:
            Tuple of (status, error_message)
            Status can be: 'RUNNING', 'SUCCEEDED', 'FAILED', 'ABORTED', etc.
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
            error = f"Failed to check job status: {str(e)}"
            logger.error(error)
            return 'FAILED', error

    @classmethod
    def get_job_results(cls, run_id: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Get results from a completed APIFY job.

        Returns:
            Tuple of (results_list, error_message)
        """
        token = cls.get_api_token()
        if not token:
            return [], "APIFY token not configured"

        try:
            response = requests.get(
                f"{cls.BASE_URL}/actor-runs/{run_id}/dataset/items",
                params={'token': token},
                timeout=60,  # Results can be large
            )
            response.raise_for_status()
            results = response.json()

            logger.info(f"Retrieved {len(results)} results from APIFY job {run_id}")
            return results, None

        except requests.RequestException as e:
            error = f"Failed to get job results: {str(e)}"
            logger.error(error)
            return [], error

    @classmethod
    def process_listing_data(cls, data: Dict, host: User) -> Tuple[Optional[Listing], str]:
        """
        Process a single listing from APIFY response and create/update in database.

        Args:
            data: Raw listing data from APIFY
            host: User to assign as host

        Returns:
            Tuple of (listing, status) where status is 'created', 'updated', or 'error'
        """
        try:
            airbnb_id = str(data.get('id', ''))
            if not airbnb_id:
                url = data.get('url', '')
                airbnb_id = cls.extract_airbnb_id(url) or ''

            if not airbnb_id:
                logger.warning("No Airbnb ID found in listing data")
                return None, 'error'

            # Check if listing already exists
            listing, created = Listing.objects.get_or_create(
                airbnb_id=airbnb_id,
                defaults={'host': host, 'title': data.get('name', 'Untitled'), 'description': '', 'price_per_night': 0}
            )

            # Update listing fields
            listing.title = data.get('name') or data.get('title') or listing.title
            listing.description = data.get('description', '') or data.get('htmlDescription', {}).get('htmlText', '')
            listing.airbnb_url = data.get('url', '')

            # Property type mapping
            property_type_raw = (data.get('propertyType') or data.get('roomType') or '').lower()
            if 'entire' in property_type_raw:
                listing.property_type = Listing.PropertyType.ENTIRE_PLACE
            elif 'private' in property_type_raw:
                listing.property_type = Listing.PropertyType.PRIVATE_ROOM
            elif 'shared' in property_type_raw:
                listing.property_type = Listing.PropertyType.SHARED_ROOM

            # Capacity - from personCapacity or subDescription
            listing.max_guests = data.get('personCapacity') or listing.max_guests
            sub_desc = data.get('subDescription', {})
            if isinstance(sub_desc, dict):
                items = sub_desc.get('items', [])
                for item in items:
                    item_lower = str(item).lower()
                    if 'bedroom' in item_lower:
                        match = re.search(r'(\d+)', item)
                        if match:
                            listing.bedrooms = int(match.group(1))
                    elif 'bed' in item_lower and 'bedroom' not in item_lower:
                        match = re.search(r'(\d+)', item)
                        if match:
                            listing.beds = int(match.group(1))
                    elif 'bath' in item_lower:
                        match = re.search(r'(\d+\.?\d*)', item)
                        if match:
                            listing.bathrooms = Decimal(match.group(1))
                    elif 'guest' in item_lower:
                        match = re.search(r'(\d+)', item)
                        if match:
                            listing.max_guests = int(match.group(1))

            # Location
            location = data.get('location', '')
            location_subtitle = data.get('locationSubtitle', '')
            coords = data.get('coordinates', {})

            if coords:
                listing.latitude = Decimal(str(coords.get('latitude', 0)))
                listing.longitude = Decimal(str(coords.get('longitude', 0)))

            # Try to parse city from location
            if location_subtitle:
                parts = location_subtitle.split(',')
                if len(parts) >= 1:
                    city_name = parts[0].strip()
                    city, _ = City.objects.get_or_create(
                        name=city_name,
                        defaults={'country': 'Philippines'}
                    )
                    listing.city = city

            listing.address = location_subtitle or location or listing.address or 'Address not provided'
            listing.neighborhood = location or ''

            # Pricing
            price_data = data.get('price', {})
            if isinstance(price_data, dict):
                rate = price_data.get('rate')
                if rate:
                    listing.price_per_night = Decimal(str(rate))

            # Ratings
            rating_data = data.get('rating', {})
            if isinstance(rating_data, dict):
                listing.rating = Decimal(str(rating_data.get('guestSatisfaction', 0) or 0))
                listing.reviews_count = rating_data.get('reviewsCount', 0) or 0
                listing.rating_accuracy = Decimal(str(rating_data.get('accuracy', 0) or 0))
                listing.rating_cleanliness = Decimal(str(rating_data.get('cleanliness', 0) or 0))
                listing.rating_checkin = Decimal(str(rating_data.get('checking', 0) or 0))
                listing.rating_communication = Decimal(str(rating_data.get('communication', 0) or 0))
                listing.rating_location = Decimal(str(rating_data.get('location', 0) or 0))
                listing.rating_value = Decimal(str(rating_data.get('value', 0) or 0))

            # House rules
            house_rules = data.get('houseRules', {})
            if isinstance(house_rules, dict):
                general = house_rules.get('general', [])
                for section in general:
                    if isinstance(section, dict):
                        values = section.get('values', [])
                        for rule in values:
                            if isinstance(rule, dict):
                                title = (rule.get('title') or '').lower()
                                if 'check-in' in title and 'after' in title:
                                    # Parse check-in time
                                    match = re.search(r'(\d{1,2})\s*(am|pm)', title, re.IGNORECASE)
                                    if match:
                                        hour = int(match.group(1))
                                        if match.group(2).lower() == 'pm' and hour != 12:
                                            hour += 12
                                        listing.check_in_time = f"{hour:02d}:00"
                                elif 'checkout' in title or 'check-out' in title:
                                    match = re.search(r'(\d{1,2})\s*(am|pm)', title, re.IGNORECASE)
                                    if match:
                                        hour = int(match.group(1))
                                        if match.group(2).lower() == 'pm' and hour != 12:
                                            hour += 12
                                        listing.check_out_time = f"{hour:02d}:00"
                                elif 'self check-in' in title:
                                    listing.self_checkin = True
                                    additional_info = rule.get('additionalInfo', '')
                                    if additional_info:
                                        listing.checkin_method = additional_info

            # Highlights
            highlights = data.get('highlights', [])
            if highlights:
                listing.highlights = highlights

            # Reviews (store as JSON)
            reviews = data.get('reviews', [])
            if reviews:
                listing.reviews = reviews[:20]  # Limit stored reviews

            # Status - set to active if synced
            if listing.status == Listing.Status.DRAFT:
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
            logger.error(f"Error processing listing: {e}")
            return None, 'error'

    @classmethod
    def _process_amenities(cls, listing: Listing, amenities_data: List) -> None:
        """Process and link amenities to listing."""
        if not amenities_data:
            return

        # Clear existing amenities
        ListingAmenityMapping.objects.filter(listing=listing).delete()

        for category_data in amenities_data:
            if not isinstance(category_data, dict):
                continue

            category_name = category_data.get('title', 'Features')
            values = category_data.get('values', [])

            # Map category
            category_map = {
                'essentials': ListingAmenity.AmenityCategory.ESSENTIALS,
                'features': ListingAmenity.AmenityCategory.FEATURES,
                'location': ListingAmenity.AmenityCategory.LOCATION,
                'safety': ListingAmenity.AmenityCategory.SAFETY,
            }
            category = category_map.get(category_name.lower(), ListingAmenity.AmenityCategory.FEATURES)

            for amenity_item in values:
                if not isinstance(amenity_item, dict):
                    continue

                name = amenity_item.get('title', '')
                available = amenity_item.get('available', True)

                if not name or not available:
                    continue

                # Get or create amenity
                amenity, _ = ListingAmenity.objects.get_or_create(
                    name=name,
                    defaults={'category': category}
                )

                # Create mapping
                ListingAmenityMapping.objects.get_or_create(
                    listing=listing,
                    amenity=amenity,
                )

    @classmethod
    def _process_images(cls, listing: Listing, images_data: List) -> None:
        """Download and store listing images."""
        if not images_data:
            return

        # Keep track of existing images to avoid duplicates
        existing_count = listing.images.count()

        for i, image_data in enumerate(images_data[:20]):  # Limit to 20 images
            if not isinstance(image_data, dict):
                continue

            image_url = image_data.get('imageUrl') or image_data.get('url')
            if not image_url:
                continue

            caption = image_data.get('caption', '')

            try:
                # Download image
                response = requests.get(image_url, timeout=30)
                response.raise_for_status()

                # Create filename
                filename = f"airbnb_{listing.airbnb_id}_{i}.jpg"

                # Save image
                image_file = ContentFile(response.content, name=filename)

                listing_image = ListingImage.objects.create(
                    listing=listing,
                    caption=caption,
                    is_primary=(i == 0 and existing_count == 0),
                    order=existing_count + i,
                )
                listing_image.image.save(filename, image_file)

            except Exception as e:
                logger.warning(f"Failed to download image {image_url}: {e}")
                continue

    @classmethod
    def sync_and_wait(cls, urls: List[str], host: User, timeout: int = 300) -> Dict:
        """
        Start a sync job, wait for completion, and process results.

        Args:
            urls: List of Airbnb URLs to sync
            host: User to assign as host for new listings
            timeout: Maximum wait time in seconds

        Returns:
            Dict with sync results
        """
        results = {
            'success': False,
            'run_id': None,
            'created': 0,
            'updated': 0,
            'errors': [],
        }

        # Start job
        run_id, error = cls.start_sync_job(urls)
        if error:
            results['errors'].append(error)
            return results

        results['run_id'] = run_id

        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < timeout:
            status, error = cls.check_job_status(run_id)

            if error:
                results['errors'].append(error)
                break

            if status == 'SUCCEEDED':
                # Get and process results
                listings_data, error = cls.get_job_results(run_id)
                if error:
                    results['errors'].append(error)
                    break

                for data in listings_data:
                    listing, status = cls.process_listing_data(data, host)
                    if status == 'created':
                        results['created'] += 1
                    elif status == 'updated':
                        results['updated'] += 1
                    elif status == 'error':
                        results['errors'].append(f"Failed to process: {data.get('url', 'unknown')}")

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
                results['errors'].append(f"Job {status}")
                # Update job record
                job = AirbnbSyncJob.objects.filter(run_id=run_id).first()
                if job:
                    job.status = AirbnbSyncJob.Status.FAILED
                    job.error_message = f"Job {status}"
                    job.completed_at = timezone.now()
                    job.save()
                break

            time.sleep(cls.POLL_INTERVAL)

        return results
