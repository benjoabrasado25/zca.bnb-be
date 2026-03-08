"""
Amadeus Hotel API Service - Syncs hotels from Amadeus API.

Uses Amadeus Hotel List API to fetch hotel data for Philippines.
Generates Klook search links for affiliate matching.
"""

import logging
import uuid
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import requests
from django.conf import settings
from django.utils import timezone

from listings.models import Listing, City
from users.models import User
from .models import AmadeusSyncJob

logger = logging.getLogger(__name__)


# Philippine IATA city codes
PHILIPPINE_CITY_CODES = {
    'MNL': 'Manila',
    'CEB': 'Cebu',
    'DVO': 'Davao',
    'ILO': 'Iloilo',
    'CRK': 'Clark',
    'KLO': 'Kalibo',
    'BCD': 'Bacolod',
    'TAG': 'Tagbilaran',
    'PPS': 'Puerto Princesa',
    'USU': 'Busuanga',
    'MPH': 'Caticlan',  # Boracay
    'CGY': 'Cagayan de Oro',
    'GES': 'General Santos',
    'ZAM': 'Zamboanga',
    'TAC': 'Tacloban',
    'LAO': 'Laoag',
    'SFS': 'Subic Bay',
    'DGT': 'Dumaguete',
    'CYP': 'Calbayog',
}


class AmadeusAPIError(Exception):
    """Raised when Amadeus API returns an error."""
    pass


class AmadeusHotelService:
    """Service for syncing hotels from Amadeus API."""

    AUTH_URL = 'https://api.amadeus.com/v1/security/oauth2/token'
    HOTEL_LIST_URL = 'https://api.amadeus.com/v1/reference-data/locations/hotels/by-city'
    HOTEL_BY_GEOCODE_URL = 'https://api.amadeus.com/v1/reference-data/locations/hotels/by-geocode'
    TIMEOUT = 30

    _access_token = None
    _token_expires_at = None

    @classmethod
    def get_credentials(cls) -> Tuple[Optional[str], Optional[str]]:
        """Get Amadeus API credentials from settings."""
        api_key = getattr(settings, 'AMADEUS_API_KEY', None)
        api_secret = getattr(settings, 'AMADEUS_API_SECRET', None)
        return api_key, api_secret

    @classmethod
    def get_access_token(cls, force_refresh: bool = False) -> Optional[str]:
        """Get or refresh Amadeus OAuth2 access token."""
        # Check if we have a valid cached token
        if not force_refresh and cls._access_token and cls._token_expires_at:
            if timezone.now() < cls._token_expires_at:
                return cls._access_token

        api_key, api_secret = cls.get_credentials()
        if not api_key or not api_secret:
            logger.error("Amadeus API credentials not configured")
            return None

        try:
            response = requests.post(
                cls.AUTH_URL,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': api_key,
                    'client_secret': api_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=cls.TIMEOUT,
            )

            if response.status_code != 200:
                logger.error(f"Amadeus auth failed: {response.status_code} - {response.text}")
                return None

            data = response.json()
            cls._access_token = data.get('access_token')
            expires_in = data.get('expires_in', 1799)  # Default 30 mins
            cls._token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in - 60)

            logger.info("Amadeus access token obtained successfully")
            return cls._access_token

        except requests.RequestException as e:
            logger.error(f"Amadeus auth request failed: {e}")
            return None

    @classmethod
    def fetch_hotels_by_city(cls, city_code: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Fetch hotels for a city using Amadeus Hotel List API.

        Args:
            city_code: IATA city code (e.g., MNL, CEB)

        Returns:
            Tuple of (hotels_list, error_message)
        """
        token = cls.get_access_token()
        if not token:
            return [], "Failed to obtain Amadeus access token"

        try:
            response = requests.get(
                cls.HOTEL_LIST_URL,
                params={
                    'cityCode': city_code,
                    'radius': 100,
                    'radiusUnit': 'KM',
                    'hotelSource': 'ALL',
                },
                headers={
                    'Authorization': f'Bearer {token}',
                    'Accept': 'application/json',
                },
                timeout=60,
            )

            if response.status_code == 401:
                # Token expired, retry with fresh token
                token = cls.get_access_token(force_refresh=True)
                if not token:
                    return [], "Failed to refresh Amadeus access token"

                response = requests.get(
                    cls.HOTEL_LIST_URL,
                    params={
                        'cityCode': city_code,
                        'radius': 100,
                        'radiusUnit': 'KM',
                        'hotelSource': 'ALL',
                    },
                    headers={
                        'Authorization': f'Bearer {token}',
                        'Accept': 'application/json',
                    },
                    timeout=60,
                )

            if response.status_code == 404:
                return [], f"No hotels found for city code: {city_code}"

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('errors', [{}])[0].get('detail', response.text)
                return [], f"Amadeus API error: {error_msg}"

            data = response.json()
            hotels = data.get('data', [])
            logger.info(f"Found {len(hotels)} hotels in {city_code}")
            return hotels, None

        except requests.RequestException as e:
            return [], f"Request failed: {str(e)}"

    @classmethod
    def fetch_hotels_by_geocode(
        cls,
        latitude: float,
        longitude: float,
        radius: int = 50
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Fetch hotels near coordinates using Amadeus API.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            radius: Search radius in km

        Returns:
            Tuple of (hotels_list, error_message)
        """
        token = cls.get_access_token()
        if not token:
            return [], "Failed to obtain Amadeus access token"

        try:
            response = requests.get(
                cls.HOTEL_BY_GEOCODE_URL,
                params={
                    'latitude': latitude,
                    'longitude': longitude,
                    'radius': radius,
                    'radiusUnit': 'KM',
                    'hotelSource': 'ALL',
                },
                headers={
                    'Authorization': f'Bearer {token}',
                    'Accept': 'application/json',
                },
                timeout=60,
            )

            if response.status_code != 200:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('errors', [{}])[0].get('detail', response.text)
                return [], f"Amadeus API error: {error_msg}"

            data = response.json()
            hotels = data.get('data', [])
            logger.info(f"Found {len(hotels)} hotels near ({latitude}, {longitude})")
            return hotels, None

        except requests.RequestException as e:
            return [], f"Request failed: {str(e)}"

    @classmethod
    def process_hotel_data(
        cls,
        hotel_data: Dict,
        host: User,
        city: Optional[City] = None
    ) -> Tuple[Optional[Listing], str]:
        """
        Process Amadeus hotel data and create/update a listing.

        Args:
            hotel_data: Raw hotel data from Amadeus
            host: User to assign as host
            city: City model instance

        Returns:
            Tuple of (listing, status) where status is 'created', 'updated', or 'error: <message>'
        """
        try:
            hotel_id = hotel_data.get('hotelId', '')
            if not hotel_id:
                return None, 'error: No hotel ID found'

            name = hotel_data.get('name', 'Unnamed Hotel')

            # Get or create by amadeus_hotel_id
            listing, created = Listing.objects.get_or_create(
                amadeus_hotel_id=hotel_id,
                defaults={
                    'host': host,
                    'title': name,
                    'description': f"Hotel in {city.name if city else 'Philippines'}",
                    'price_per_night': Decimal('0'),  # Will be updated from offers
                    'address': 'Address pending',
                    'property_category': Listing.PropertyCategory.HOTEL,
                    'property_type': Listing.PropertyType.PRIVATE_ROOM,
                    'status': Listing.Status.DRAFT,
                }
            )

            # Update fields
            listing.title = name
            listing.amadeus_chain_code = hotel_data.get('chainCode', '')

            # Location
            geo_code = hotel_data.get('geoCode', {})
            if geo_code:
                if geo_code.get('latitude'):
                    listing.latitude = Decimal(str(geo_code['latitude']))
                if geo_code.get('longitude'):
                    listing.longitude = Decimal(str(geo_code['longitude']))

            # Address
            address = hotel_data.get('address', {})
            if address:
                address_parts = []
                if address.get('lines'):
                    address_parts.extend(address['lines'])
                if address.get('cityName'):
                    address_parts.append(address['cityName'])
                if address.get('postalCode'):
                    address_parts.append(address['postalCode'])
                if address.get('countryCode'):
                    address_parts.append(address['countryCode'])

                listing.address = ', '.join(filter(None, address_parts)) or listing.address

            # City
            if city:
                listing.city = city
            elif address.get('cityName'):
                city_obj, _ = City.objects.get_or_create(
                    name=address['cityName'],
                    defaults={'country': 'Philippines'}
                )
                listing.city = city_obj

            # Distance info (for reference)
            distance = hotel_data.get('distance', {})
            if distance:
                dist_value = distance.get('value', 0)
                dist_unit = distance.get('unit', 'KM')
                # Could store this in a field if needed

            listing.amadeus_last_synced = timezone.now()
            listing.save()

            status = 'created' if created else 'updated'
            logger.info(f"Processed hotel {hotel_id} ({name}): {status}")
            return listing, status

        except Exception as e:
            logger.error(f"Error processing hotel: {e}", exc_info=True)
            return None, f'error: {str(e)}'

    @classmethod
    def sync_city(
        cls,
        city_code: str,
        host: User
    ) -> Dict:
        """
        Sync all hotels for a city.

        Args:
            city_code: IATA city code
            host: User to assign as host

        Returns:
            Dict with sync results
        """
        job_id = f"amadeus_{city_code}_{uuid.uuid4().hex[:8]}"

        results = {
            'success': False,
            'job_id': job_id,
            'city_code': city_code,
            'found': 0,
            'created': 0,
            'updated': 0,
            'errors': [],
            'listings': [],
        }

        # Get or create city
        city_name = PHILIPPINE_CITY_CODES.get(city_code, city_code)
        city, _ = City.objects.get_or_create(
            name=city_name,
            defaults={'country': 'Philippines'}
        )

        # Create job record
        job = AmadeusSyncJob.objects.create(
            job_id=job_id,
            sync_type=AmadeusSyncJob.SyncType.CITY_SEARCH,
            city_code=city_code,
            status=AmadeusSyncJob.Status.RUNNING,
        )

        try:
            # Fetch hotels
            hotels, error = cls.fetch_hotels_by_city(city_code)
            if error:
                results['errors'].append(error)
                job.status = AmadeusSyncJob.Status.FAILED
                job.error_message = error
                job.completed_at = timezone.now()
                job.save()
                return results

            results['found'] = len(hotels)
            job.hotels_found = len(hotels)
            job.raw_response = {'hotels_count': len(hotels)}
            job.save()

            # Process each hotel
            for hotel_data in hotels:
                listing, status = cls.process_hotel_data(hotel_data, host, city)

                if listing:
                    results['listings'].append(listing.id)
                    if status == 'created':
                        results['created'] += 1
                    elif status == 'updated':
                        results['updated'] += 1
                elif status.startswith('error:'):
                    results['errors'].append(status)

            # Update job
            job.status = AmadeusSyncJob.Status.SUCCEEDED
            job.hotels_created = results['created']
            job.hotels_updated = results['updated']
            job.completed_at = timezone.now()
            job.save()

            results['success'] = True

        except Exception as e:
            error_msg = str(e)
            results['errors'].append(error_msg)
            job.status = AmadeusSyncJob.Status.FAILED
            job.error_message = error_msg
            job.completed_at = timezone.now()
            job.save()
            logger.error(f"Sync failed: {e}", exc_info=True)

        return results

    @classmethod
    def sync_all_philippine_cities(cls, host: User) -> Dict:
        """
        Sync hotels for all major Philippine cities.

        Args:
            host: User to assign as host

        Returns:
            Dict with combined sync results
        """
        results = {
            'success': True,
            'cities_synced': 0,
            'total_found': 0,
            'total_created': 0,
            'total_updated': 0,
            'city_results': {},
            'errors': [],
        }

        for city_code, city_name in PHILIPPINE_CITY_CODES.items():
            logger.info(f"Syncing hotels for {city_name} ({city_code})")

            city_result = cls.sync_city(city_code, host)
            results['city_results'][city_code] = city_result

            if city_result['success']:
                results['cities_synced'] += 1
                results['total_found'] += city_result['found']
                results['total_created'] += city_result['created']
                results['total_updated'] += city_result['updated']
            else:
                results['errors'].extend(city_result['errors'])

        return results

    @classmethod
    def test_connection(cls) -> Tuple[bool, str]:
        """
        Test Amadeus API connection.

        Returns:
            Tuple of (success, message)
        """
        api_key, api_secret = cls.get_credentials()
        if not api_key or not api_secret:
            return False, "AMADEUS_API_KEY and AMADEUS_API_SECRET not configured in settings"

        token = cls.get_access_token(force_refresh=True)
        if token:
            return True, "Successfully connected to Amadeus API"
        else:
            return False, "Failed to authenticate with Amadeus API"
