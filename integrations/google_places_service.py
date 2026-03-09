"""
Google Places API (New) Service - Search and import hotels.

Uses the new Google Places API for hotel search with photos and details.
"""

import logging
import uuid
import time
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from listings.models import Listing, ListingImage, ListingAmenity, ListingAmenityMapping, City
from users.models import User
from .models import GooglePlacesSyncJob

logger = logging.getLogger(__name__)


# Philippine cities for quick selection
PHILIPPINE_CITIES = [
    'Manila',
    'Makati',
    'Taguig',
    'Pasay',
    'Cebu City',
    'Davao City',
    'Baguio',
    'Boracay',
    'Palawan',
    'Puerto Princesa',
    'Tagaytay',
    'Subic',
    'Clark',
    'Iloilo City',
    'Bacolod',
    'Dumaguete',
    'Siargao',
    'El Nido',
    'Coron',
    'Bohol',
]


class GooglePlacesService:
    """Service for searching hotels via Google Places API (New)."""

    BASE_URL = 'https://places.googleapis.com/v1/places'
    TIMEOUT = 30
    MAX_PHOTOS = 10

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Get Google Places API key from settings."""
        return getattr(settings, 'GOOGLE_PLACES_API_KEY', None) or None

    @classmethod
    def test_connection(cls) -> Tuple[bool, str]:
        """Test Google Places API connection."""
        api_key = cls.get_api_key()
        if not api_key:
            return False, "GOOGLE_PLACES_API_KEY not configured in settings"

        # Try a simple search to verify API key works
        try:
            response = requests.post(
                f"{cls.BASE_URL}:searchText",
                headers={
                    'Content-Type': 'application/json',
                    'X-Goog-Api-Key': api_key,
                    'X-Goog-FieldMask': 'places.displayName',
                },
                json={
                    'textQuery': 'hotel in Manila',
                    'maxResultCount': 1,
                },
                timeout=cls.TIMEOUT,
            )

            if response.status_code == 200:
                return True, "Successfully connected to Google Places API"
            elif response.status_code == 403:
                return False, "API key is invalid or Places API is not enabled"
            else:
                error = response.json().get('error', {}).get('message', response.text)
                return False, f"API error: {error}"

        except requests.RequestException as e:
            return False, f"Connection failed: {str(e)}"

    @classmethod
    def search_hotels(cls, query: str, max_results: int = 20) -> Tuple[List[Dict], Optional[str]]:
        """
        Search for hotels using Google Places Text Search.

        Args:
            query: Search query (e.g., "hotels in Makati")
            max_results: Maximum number of results (1-20)

        Returns:
            Tuple of (places_list, error_message)
        """
        api_key = cls.get_api_key()
        if not api_key:
            return [], "GOOGLE_PLACES_API_KEY not configured"

        try:
            response = requests.post(
                f"{cls.BASE_URL}:searchText",
                headers={
                    'Content-Type': 'application/json',
                    'X-Goog-Api-Key': api_key,
                    'X-Goog-FieldMask': ','.join([
                        'places.id',
                        'places.displayName',
                        'places.formattedAddress',
                        'places.location',
                        'places.rating',
                        'places.userRatingCount',
                        'places.photos',
                        'places.websiteUri',
                        'places.googleMapsUri',
                        'places.types',
                        'places.priceLevel',
                    ]),
                },
                json={
                    'textQuery': query,
                    'includedType': 'lodging',
                    'maxResultCount': min(max_results, 20),
                    'languageCode': 'en',
                },
                timeout=60,
            )

            if response.status_code != 200:
                error = response.json().get('error', {}).get('message', response.text)
                return [], f"Search failed: {error}"

            data = response.json()
            places = data.get('places', [])
            logger.info(f"Found {len(places)} hotels for query: {query}")
            return places, None

        except requests.RequestException as e:
            return [], f"Request failed: {str(e)}"

    @classmethod
    def get_place_details(cls, place_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Get detailed information about a place including amenities.

        Args:
            place_id: Google Place ID

        Returns:
            Tuple of (place_details, error_message)
        """
        api_key = cls.get_api_key()
        if not api_key:
            return None, "GOOGLE_PLACES_API_KEY not configured"

        try:
            response = requests.get(
                f"{cls.BASE_URL}/{place_id}",
                headers={
                    'Content-Type': 'application/json',
                    'X-Goog-Api-Key': api_key,
                    'X-Goog-FieldMask': ','.join([
                        'id',
                        'displayName',
                        'formattedAddress',
                        'location',
                        'rating',
                        'userRatingCount',
                        'photos',
                        'websiteUri',
                        'googleMapsUri',
                        'types',
                        'priceLevel',
                        'editorialSummary',
                        'reviews',
                        'currentOpeningHours',
                        'internationalPhoneNumber',
                        # Amenities - returned as boolean fields
                        'accessibilityOptions',
                        'parkingOptions',
                        'paymentOptions',
                        'amenities',
                    ]),
                },
                timeout=cls.TIMEOUT,
            )

            if response.status_code != 200:
                error = response.json().get('error', {}).get('message', response.text)
                return None, f"Failed to get details: {error}"

            return response.json(), None

        except requests.RequestException as e:
            return None, f"Request failed: {str(e)}"

    @classmethod
    def get_photo_url(cls, photo_name: str, max_width: int = 800) -> Optional[str]:
        """
        Get a usable photo URL from Google Places photo reference.

        Args:
            photo_name: Photo resource name from Places API
            max_width: Maximum width in pixels

        Returns:
            Photo URL or None
        """
        api_key = cls.get_api_key()
        if not api_key or not photo_name:
            return None

        # The new Places API returns photo names like "places/PLACE_ID/photos/PHOTO_REF"
        return f"https://places.googleapis.com/v1/{photo_name}/media?maxWidthPx={max_width}&key={api_key}"

    @classmethod
    def download_photo(cls, photo_url: str) -> Optional[bytes]:
        """Download a photo from URL."""
        try:
            response = requests.get(photo_url, timeout=30)
            if response.status_code == 200:
                return response.content
            return None
        except requests.RequestException:
            return None

    @classmethod
    def extract_amenities_text(cls, place_data: Dict) -> List[str]:
        """
        Extract amenities as text list from place data.

        Args:
            place_data: Place details from Google Places API

        Returns:
            List of amenity strings
        """
        amenities = []

        # From types
        type_mapping = {
            'lodging': 'Accommodation',
            'hotel': 'Hotel',
            'resort': 'Resort',
            'spa': 'Spa',
            'gym': 'Fitness Center',
            'swimming_pool': 'Swimming Pool',
            'restaurant': 'Restaurant',
            'bar': 'Bar',
            'cafe': 'Cafe',
            'parking': 'Parking',
            'airport_shuttle': 'Airport Shuttle',
        }

        types = place_data.get('types', [])
        for t in types:
            if t in type_mapping:
                amenities.append(type_mapping[t])

        # Parking options
        parking = place_data.get('parkingOptions', {})
        if parking.get('freeParking') or parking.get('freeParkingLot'):
            amenities.append('Free Parking')
        elif parking.get('paidParking') or parking.get('paidParkingLot'):
            amenities.append('Paid Parking')
        if parking.get('valetParking'):
            amenities.append('Valet Parking')

        # Accessibility
        accessibility = place_data.get('accessibilityOptions', {})
        if accessibility.get('wheelchairAccessibleEntrance'):
            amenities.append('Wheelchair Accessible Entrance')
        if accessibility.get('wheelchairAccessibleRestroom'):
            amenities.append('Wheelchair Accessible Restroom')
        if accessibility.get('wheelchairAccessibleSeating'):
            amenities.append('Wheelchair Accessible Seating')

        # Payment options
        payment = place_data.get('paymentOptions', {})
        if payment.get('acceptsCreditCards'):
            amenities.append('Accepts Credit Cards')
        if payment.get('acceptsCashOnly'):
            amenities.append('Cash Only')

        return list(set(amenities))  # Remove duplicates

    @classmethod
    def process_place_to_listing(
        cls,
        place_data: Dict,
        host: User,
        city: Optional[City] = None,
        download_images: bool = True
    ) -> Tuple[Optional[Listing], str]:
        """
        Process Google Place data and create/update a listing.

        Args:
            place_data: Place data from Google Places API
            host: User to assign as host
            city: City model instance
            download_images: Whether to download and save images

        Returns:
            Tuple of (listing, status) where status is 'created', 'updated', or 'error: <message>'
        """
        try:
            place_id = place_data.get('id', '')
            if not place_id:
                return None, 'error: No place ID found'

            display_name = place_data.get('displayName', {})
            name = display_name.get('text', 'Unnamed Hotel') if isinstance(display_name, dict) else str(display_name)

            # Get or create by google_place_id
            listing, created = Listing.objects.get_or_create(
                google_place_id=place_id,
                defaults={
                    'host': host,
                    'title': name,
                    'description': '',
                    'price_per_night': Decimal('0'),
                    'address': place_data.get('formattedAddress', 'Address pending'),
                    'property_category': Listing.PropertyCategory.HOTEL,
                    'property_type': Listing.PropertyType.PRIVATE_ROOM,
                    'status': Listing.Status.DRAFT,
                }
            )

            # Update fields
            listing.title = name
            listing.address = place_data.get('formattedAddress', '') or listing.address
            listing.google_maps_url = place_data.get('googleMapsUri', '')

            # Location
            location = place_data.get('location', {})
            if location.get('latitude'):
                listing.latitude = Decimal(str(location['latitude']))
            if location.get('longitude'):
                listing.longitude = Decimal(str(location['longitude']))

            # Rating
            if place_data.get('rating'):
                listing.rating = Decimal(str(place_data['rating']))
            if place_data.get('userRatingCount'):
                listing.reviews_count = place_data['userRatingCount']

            # Description from editorial summary
            editorial = place_data.get('editorialSummary', {})
            if editorial and isinstance(editorial, dict):
                listing.description = editorial.get('text', '') or listing.description

            # City
            if city:
                listing.city = city
            elif not listing.city:
                # Try to extract city from address
                address = place_data.get('formattedAddress', '')
                if address:
                    # Simple extraction - take second-to-last part before country
                    parts = [p.strip() for p in address.split(',')]
                    if len(parts) >= 2:
                        city_name = parts[-2] if 'Philippines' in parts[-1] else parts[-1]
                        city_obj, _ = City.objects.get_or_create(
                            name=city_name,
                            defaults={'country': 'Philippines'}
                        )
                        listing.city = city_obj

            # Extract and save amenities as text in highlights
            amenities_list = cls.extract_amenities_text(place_data)
            if amenities_list:
                listing.highlights = amenities_list

            # Process amenities into the amenity mapping table too
            cls._process_amenities(listing, amenities_list)

            listing.save()

            # Download and save photos
            if download_images:
                photos = place_data.get('photos', [])
                if photos:
                    cls._process_photos(listing, photos)

            status = 'created' if created else 'updated'
            logger.info(f"Processed place {place_id} ({name}): {status}")
            return listing, status

        except Exception as e:
            logger.error(f"Error processing place: {e}", exc_info=True)
            return None, f'error: {str(e)}'

    @classmethod
    def _process_amenities(cls, listing: Listing, amenities_list: List[str]):
        """Process amenities and create mappings."""
        if not amenities_list:
            return

        for amenity_name in amenities_list:
            amenity, _ = ListingAmenity.objects.get_or_create(
                name=amenity_name,
                defaults={'category': ListingAmenity.AmenityCategory.FEATURES}
            )
            ListingAmenityMapping.objects.get_or_create(
                listing=listing,
                amenity=amenity
            )

    @classmethod
    def _process_photos(cls, listing: Listing, photos: List[Dict]):
        """Download and save photos for a listing."""
        # Clear existing images if re-syncing
        if listing.images.exists():
            listing.images.all().delete()

        for i, photo in enumerate(photos[:cls.MAX_PHOTOS]):
            photo_name = photo.get('name')
            if not photo_name:
                continue

            photo_url = cls.get_photo_url(photo_name, max_width=1200)
            if not photo_url:
                continue

            try:
                content = cls.download_photo(photo_url)
                if not content:
                    continue

                filename = f"google_{listing.google_place_id}_{i}.jpg"
                listing_image = ListingImage(
                    listing=listing,
                    caption='',
                    is_primary=(i == 0),
                    order=i,
                )
                listing_image.image.save(filename, ContentFile(content), save=True)

                # Small delay to be nice to the API
                time.sleep(0.2)

            except Exception as e:
                logger.warning(f"Failed to download photo: {e}")
                continue

    @classmethod
    def sync_hotels_by_city(cls, city_name: str, host: User, download_images: bool = True) -> Dict:
        """
        Search and import hotels for a city.

        Args:
            city_name: City name to search
            host: User to assign as host
            download_images: Whether to download images

        Returns:
            Dict with sync results
        """
        job_id = f"google_{city_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"

        results = {
            'success': False,
            'job_id': job_id,
            'city_name': city_name,
            'found': 0,
            'created': 0,
            'updated': 0,
            'errors': [],
            'listings': [],
        }

        # Get or create city
        city, _ = City.objects.get_or_create(
            name=city_name,
            defaults={'country': 'Philippines'}
        )

        # Create job record
        job = GooglePlacesSyncJob.objects.create(
            job_id=job_id,
            search_query=f"hotels in {city_name}",
            city_name=city_name,
            status=GooglePlacesSyncJob.Status.RUNNING,
        )

        try:
            # Search for hotels
            places, error = cls.search_hotels(f"hotels in {city_name}, Philippines")
            if error:
                results['errors'].append(error)
                job.status = GooglePlacesSyncJob.Status.FAILED
                job.error_message = error
                job.completed_at = timezone.now()
                job.save()
                return results

            results['found'] = len(places)
            job.hotels_found = len(places)
            job.save()

            # Process each place
            for place_data in places:
                listing, status = cls.process_place_to_listing(
                    place_data, host, city, download_images
                )

                if listing:
                    results['listings'].append(listing.id)
                    if status == 'created':
                        results['created'] += 1
                    elif status == 'updated':
                        results['updated'] += 1
                elif status.startswith('error:'):
                    results['errors'].append(status)

            # Update job
            job.status = GooglePlacesSyncJob.Status.SUCCEEDED
            job.hotels_created = results['created']
            job.hotels_updated = results['updated']
            job.completed_at = timezone.now()
            job.save()

            results['success'] = True

        except Exception as e:
            error_msg = str(e)
            results['errors'].append(error_msg)
            job.status = GooglePlacesSyncJob.Status.FAILED
            job.error_message = error_msg
            job.completed_at = timezone.now()
            job.save()
            logger.error(f"Sync failed: {e}", exc_info=True)

        return results
