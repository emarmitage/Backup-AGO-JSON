'''
AGO Backup Script
backs up AGO items (excluding layers) from multiple accounts.
Note that the items need to be shared with the account used to do the backing up

Supports backing up to multiple folders with variable retention policies.


Isaac Cave
Feb 15th, 2023
v0.1

v0.2
-Added more backup types to whitelist
-optimized type search logic

v0.3
March 3rd, 2023
-Added support for multiple folders
-Added support for variable retention policies
-Better logging
-Updated description

Emma Armitage Tweaks
Aug 27, 2024
-Change AGO account credentials to pull from GitHub Secrets
-Selected backup types to only include experience builder & web maps
-Added ability to backup from specific ago folders 
-Save backup json to object storage
-Delete backups in object storage older than 7 days
'''


#%%
# Imports
from arcgis.gis import GIS, User
from datetime import datetime, timedelta, timezone
import json
import os
import boto3

#%%
# Configuration
maphub_accounts = [
    os.environ['AGO_USER'],
    ] # Accounts to backup from. Items must be shared with PX.SCGIS
max_search = 100 # Maximum number of items

backup_types = ["Web Map", "Web Experience"]

ago_folder_name = 'Badger Sightings Survey'

retention_days = 7

#%%
# Credentials
agol_username = os.environ['AGO_USER']
agol_password = os.environ['AGO_PASS']
obj_store_user = os.environ['SIES_OBJ_STORE_USER']
obj_store_api_key = os.environ['SIES_OBJ_STORE_API_KEY']
obj_store_host = os.environ['OBJ_STORE_HOST']
bucket_name = os.environ['OBJ_STORE_BUCKET']

url = 'https://governmentofbc.maps.arcgis.com' # change to your url, whether maphub, geohub, or other
gis = GIS(url, agol_username, agol_password)
user = gis.users.get(agol_username)

# connect to object storage
boto_resource = boto3.resource(service_name='s3',
                               aws_access_key_id=obj_store_user,
                               aws_secret_access_key=obj_store_api_key,
                               endpoint_url=f'https://{obj_store_host}')

#%%
# Function setup
class jsonItem:
    def __init__(self,primary_id):
        self.primary_id = primary_id
        self.change_list = []
        self.prim_wm_item = gis.content.get(self.primary_id)
        self.prim_wm_json = self.prim_wm_item.get_data()
    def json_backup(self, folder_name): #backs up the json to object storage
        today = datetime.today().strftime("%Y_%m_%d")
        item_title = self.prim_wm_item.title.lower()
        self.filename = f"{today}_{item_title}_{self.primary_id}.json".replace(":", "-").replace('"', '').replace("|", "_").replace("/", "_").replace("\\", "_")
        self.ostore_path = f'ago_backups/{folder_name}/{self.filename}'

        try:
            s3_object = boto_resource.Object(bucket_name, self.ostore_path)
            s3_object.put(
                Body=json.dumps(self.prim_wm_json),
                ContentType='application/json'
            )

            print(f"JSON file {self.filename} has been uploaded to s3://{bucket_name}/{self.ostore_path}")

        except Exception as e:
            print(f"An error occurred: {e}")

# Delete older backups
def delete_old_backups(folder_title):
    now = datetime.now(timezone.utc)
    threshold_date = now - timedelta(days=retention_days)
    bucket = boto_resource.Bucket(bucket_name)

    for obj in bucket.objects.filter(Prefix=f'ago_backups/{folder_title}'):
        obj_last_modified = obj.last_modified
        if obj_last_modified < threshold_date:
            try:
                obj.delete()
                print(f"Deleted old backup: {obj.key}")
            except Exception as e:
                print(f"Failed to delete {obj.key}: {e}")

#%%
# Backing up
def backup_items():
    for username in maphub_accounts:
    
        # only retrieve content from specific folders 
        folders = user.folders
        for folder in folders:
            if folder['title'] in ago_folder_name:
                folder_title_os = folder['title'].lower()
                delete_old_backups(folder_title=folder_title_os)
                
                item_list = []
                for item in user.items(folder['title']):
                    if item['type'] in backup_types:
                        item_list.append(item)
        
                for result in item_list:
                    in_id = result['id']
                    if result['type'] in backup_types:
                        print(f"backing up {in_id}")
                        item = jsonItem(in_id)
                        item.json_backup(folder_name=folder_title_os)

# execute the fucntions
if __name__ == "__main__":
    backup_items()
