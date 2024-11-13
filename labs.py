import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from planet import Session, Auth, DataClient, order_request, data_filter, reporting

# Replace with your actual API key
API_KEY = "YOUR_API_KEY_HERE"
DOWNLOAD_DIR = Path("monthly_downloads")  # Base directory to store downloaded orders

# ------------------------- User Input Functions ------------------------- #

def get_user_input():
    print("Please enter the coordinates for the area of interest (AOI).")
    print("Enter the first corner (latitude and longitude):")
    lat1 = float(input("Latitude 1: "))
    lon1 = float(input("Longitude 1: "))

    print("Enter the second corner (latitude and longitude):")
    lat2 = float(input("Latitude 2: "))
    lon2 = float(input("Longitude 2: "))

    # Create a polygon from the two corner points
    geometry = {
        "type": "Polygon",
        "coordinates": [
            [
                [lon1, lat1],
                [lon2, lat1],
                [lon2, lat2],
                [lon1, lat2],
                [lon1, lat1],
            ]
        ],
    }

    print("\nEnter the date range for data acquisition.")
    start_date_str = input("Start date (YYYY-MM-DD): ")
    end_date_str = input("End date (YYYY-MM-DD): ")

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        exit(1)

    if start_date > end_date:
        print("Start date must be before or equal to end date.")
        exit(1)

    print("\nEnter the maximum cloud cover percentage (0-100).")
    cloud_cover_input = input("Cloud cover (%): ")
    try:
        cloud_cover = float(cloud_cover_input) / 100  # Convert to fraction
        if not 0 <= cloud_cover <= 1:
            raise ValueError
    except ValueError:
        print("Invalid cloud cover value. Please enter a number between 0 and 100.")
        exit(1)

    return geometry, start_date, end_date, cloud_cover

def get_product_bundle():
    print("\nSelect the product bundle you want to order:")
    print("1. Visual")
    print("2. Analytic")
    print("3. UDM2")
    print("4. Analytic UDM2")
    choice = input("Enter the number corresponding to your choice (default 1): ") or '1'

    bundles = {
        '1': 'visual',
        '2': 'analytic',
        '3': 'udm2',
        '4': 'analytic_udm2'
    }

    return bundles.get(choice, 'visual')  # Default to 'visual' if invalid choice

def get_output_format():
    print("\nSelect the output file format:")
    print("1. Cloud Optimized GeoTIFF (COG)")
    print("2. PL_NITF")
    choice = input("Enter the number corresponding to your choice (default 1): ") or '1'

    formats = {
        '1': 'COG',
        '2': 'PL_NITF'
    }

    return formats.get(choice, 'COG')  # Default to 'COG' if invalid choice

def get_delivery_option():
    print("\nSelect your preferred delivery option:")
    print("1. Direct Download")
    print("2. Amazon S3")
    print("3. Azure Blob Storage")
    print("4. Google Cloud Storage")
    choice = input("Enter the number corresponding to your choice (default 1): ") or '1'

    return choice

def get_cloud_config(option):
    if option == '2':  # Amazon S3
        aws_access_key_id = input("Enter your AWS Access Key ID: ")
        aws_secret_access_key = input("Enter your AWS Secret Access Key: ")
        bucket = input("Enter your S3 bucket name: ")
        aws_region = input("Enter your AWS region (e.g., us-east-1): ")
        path_prefix = input("Enter path prefix (optional): ") or None
        return order_request.amazon_s3(aws_access_key_id, aws_secret_access_key, bucket, aws_region, path_prefix)
    elif option == '3':  # Azure Blob Storage
        account = input("Enter your Azure account name: ")
        container = input("Enter your Azure container name: ")
        sas_token = input("Enter your SAS token: ")
        storage_endpoint_suffix = input("Enter storage endpoint suffix (optional): ") or None
        path_prefix = input("Enter path prefix (optional): ") or None
        return order_request.azure_blob_storage(account, container, sas_token, storage_endpoint_suffix, path_prefix)
    elif option == '4':  # Google Cloud Storage
        credentials = input("Enter your GCS credentials JSON string: ")
        bucket = input("Enter your GCS bucket name: ")
        path_prefix = input("Enter path prefix (optional): ") or None
        return order_request.google_cloud_storage(credentials, bucket, path_prefix)
    else:
        return None  # Direct Download

def get_notification_preferences():
    print("\nWould you like to set up notifications for your orders?")
    print("1. No Notifications")
    print("2. Email Notifications")
    print("3. Webhook Notifications")
    choice = input("Enter the number corresponding to your choice (default 1): ") or '1'

    if choice == '2':
        email = input("Enter your email address for notifications: ")
        return order_request.notifications(email=email)
    elif choice == '3':
        webhook_url = input("Enter your webhook URL: ")
        webhook_per_order = input("Do you want one webhook per order? (yes/no, default no): ").lower() == 'yes'
        return order_request.notifications(webhook_url=webhook_url, webhook_per_order=webhook_per_order)
    else:
        return None  # No Notifications

def get_additional_filters():
    print("\nWould you like to apply additional filters? (yes/no)")
    apply = input("Choice: ").lower() == 'yes'
    additional_filters = []

    if not apply:
        return None

    # Viewing Angle Filter
    apply_view_angle = input("Filter by viewing angle? (yes/no, default no): ").lower() == 'yes'
    if apply_view_angle:
        try:
            max_view_angle = float(input("Enter maximum viewing angle (degrees): "))
            additional_filters.append(data_filter.range_filter("view_angle", lte=max_view_angle))
        except ValueError:
            print("Invalid viewing angle. Skipping this filter.")

    # Ground Sample Distance (GSD) Filter
    apply_gsd = input("Filter by Ground Sample Distance (GSD)? (yes/no, default no): ").lower() == 'yes'
    if apply_gsd:
        try:
            max_gsd = float(input("Enter maximum GSD (meters): "))
            additional_filters.append(data_filter.range_filter("gsd", lte=max_gsd))
        except ValueError:
            print("Invalid GSD value. Skipping this filter.")

    # Item Type Selection
    apply_item_type = input("Filter by item type? (yes/no, default no): ").lower() == 'yes'
    if apply_item_type:
        print("Available item types: PSScene, PSOrthoTile, REOrthoTile, etc.")
        item_type = input("Enter item type: ")
        if item_type:
            additional_filters.append(data_filter.string_in_filter("item_type", [item_type]))

    # Quality Category Filter
    apply_quality = input("Filter by quality category? (yes/no, default no): ").lower() == 'yes'
    if apply_quality:
        print("Available quality categories: standard, preview, etc.")
        quality = input("Enter quality category: ")
        if quality:
            additional_filters.append(data_filter.string_in_filter("quality_category", [quality]))

    # Specific Sensor Selection
    apply_sensor = input("Filter by specific sensor? (yes/no, default no): ").lower() == 'yes'
    if apply_sensor:
        sensor = input("Enter sensor name (e.g., 'SkySat'): ")
        if sensor:
            additional_filters.append(data_filter.string_in_filter("sensor", [sensor]))

    # Publishing Stage Filter
    apply_publishing_stage = input("Filter by publishing stage? (yes/no, default no): ").lower() == 'yes'
    if apply_publishing_stage:
        print("Available publishing stages: preview, standard, finalized")
        stage = input("Enter publishing stage: ")
        if stage:
            additional_filters.append(data_filter.string_in_filter("publishing_stage", [stage]))

    # Instrument ID Filter
    apply_instrument = input("Filter by instrument ID? (yes/no, default no): ").lower() == 'yes'
    if apply_instrument:
        instrument_id = input("Enter instrument ID: ")
        if instrument_id:
            additional_filters.append(data_filter.string_in_filter("instrument_id", [instrument_id]))

    # Shadow Percentage Filter
    apply_shadow = input("Filter by shadow percentage? (yes/no, default no): ").lower() == 'yes'
    if apply_shadow:
        try:
            max_shadow = float(input("Enter maximum shadow percentage (0-100): ")) / 100
            additional_filters.append(data_filter.range_filter("shadow_percent", lte=max_shadow))
        except ValueError:
            print("Invalid shadow percentage. Skipping this filter.")

    # Haze Percentage Filter
    apply_haze = input("Filter by haze percentage? (yes/no, default no): ").lower() == 'yes'
    if apply_haze:
        try:
            max_haze = float(input("Enter maximum haze percentage (0-100): ")) / 100
            additional_filters.append(data_filter.range_filter("haze_percent", lte=max_haze))
        except ValueError:
            print("Invalid haze percentage. Skipping this filter.")

    # Snow/Ice Percentage Filter
    apply_snow_ice = input("Filter by snow/ice percentage? (yes/no, default no): ").lower() == 'yes'
    if apply_snow_ice:
        try:
            max_snow_ice = float(input("Enter maximum snow/ice percentage (0-100): ")) / 100
            additional_filters.append(data_filter.range_filter("snow_ice_percent", lte=max_snow_ice))
        except ValueError:
            print("Invalid snow/ice percentage. Skipping this filter.")

    if additional_filters:
        return data_filter.and_filter(additional_filters)
    else:
        return None

# ------------------------- Order Request Functions ------------------------- #

def create_order_request(order_name, item_ids, geometry, product_bundle, file_format, delivery_option, notification_pref):
    tools = [order_request.clip_tool(aoi=geometry), order_request.file_format_tool(file_format)]

    # Add delivery configuration
    delivery = get_cloud_config(delivery_option)
    # Add notifications
    notifications = notification_pref

    return order_request.build_request(
        name=order_name,
        products=[
            order_request.product(
                item_ids=item_ids,
                product_bundle=product_bundle,
                item_type='PSScene'  # You might want to make this dynamic based on item_type filter
            )
        ],
        tools=tools,
        delivery=delivery,
        notifications=notifications
    )

async def gather_ids_for_month(client, item_types, geometry, month_start, month_end, limit=100, cloud_cover_max=0.15, additional_filter=None):
    base_filters = [
        data_filter.date_range_filter("acquired", gte=month_start, lte=month_end),
        data_filter.geometry_filter(geometry),
        data_filter.range_filter("cloud_cover", lte=cloud_cover_max),
    ]

    if additional_filter:
        base_filters.append(additional_filter)

    search_filter = data_filter.and_filter(base_filters)

    items = []
    async for item in client.search(item_types, search_filter=search_filter, limit=limit):
        items.append(item['id'])

    return items

async def create_and_download_order(client, order_request_obj, order_name):
    # Ensure download directory exists
    month_dir = DOWNLOAD_DIR / order_name
    month_dir.mkdir(parents=True, exist_ok=True)

    with reporting.StateBar(state='creating') as reporter:
        # Create order and track status
        order = await client.create_order(order_request_obj)
        reporter.update(state='created', order_id=order['id'])
        await client.wait(
            order['id'],
            callback=reporter.update_state,
            max_attempts=500,    # Increased from 200 to 500
            delay=10             # Increased delay between attempts to 10 seconds
        )

    # Download order to the unique monthly directory
    await client.download_order(order['id'], directory=month_dir, progress_bar=True)
    print(f"Order '{order_name}' downloaded to {month_dir}")

# ------------------------- Main Function ------------------------- #

async def main():
    # Gather user inputs
    geometry, start_date, end_date, cloud_cover_max = get_user_input()
    product_bundle = get_product_bundle()
    file_format = get_output_format()
    delivery_option = get_delivery_option()
    notification_pref = get_notification_preferences()
    additional_filter = get_additional_filters()

    auth = Auth.from_key(API_KEY)
    async with Session(auth=auth) as sess:
        data_client: DataClient = sess.client('data')
        orders_client = sess.client('orders')

        current_date = start_date

        # Loop through each month within the date range
        while current_date <= end_date:
            month_start = current_date.replace(day=1)
            # Calculate the last day of the current month
            next_month = (month_start + timedelta(days=32)).replace(day=1)
            month_end = next_month - timedelta(days=1)
            if month_end > end_date:
                month_end = end_date

            print(f"\nProcessing data from {month_start.strftime('%Y-%m-%d')} to {month_end.strftime('%Y-%m-%d')}")

            # Gather all item IDs for the current month with additional filters
            item_ids = await gather_ids_for_month(
                data_client,
                item_types=['PSScene'],
                geometry=geometry,
                month_start=month_start,
                month_end=month_end,
                cloud_cover_max=cloud_cover_max,
                additional_filter=additional_filter
            )

            # Only create an order if we have items for the month
            if item_ids:
                # Create a unique order name based on the month and year
                order_name = f"order_{month_start.strftime('%Y_%m')}"

                # Build the order request for this month
                order_request_obj = create_order_request(
                    order_name,
                    item_ids,
                    geometry,
                    product_bundle,
                    file_format,
                    delivery_option,
                    notification_pref
                )

                # Create and download the order
                await create_and_download_order(orders_client, order_request_obj, order_name)
            else:
                print(f"No items found for {month_start.strftime('%Y-%m')} with the specified criteria.")

            # Move to the next month
            current_date = next_month

    print("\nAll orders processed.")

# ------------------------- Run the Script ------------------------- #

if __name__ == "__main__":
    asyncio.run(main())
