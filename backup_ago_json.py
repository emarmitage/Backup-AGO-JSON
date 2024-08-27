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
'''


#%%
# Imports
from arcgis.gis import GIS, User
from datetime import datetime
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
        # self.folder = folder
        self.change_list = []
        self.prim_wm_item = gis.content.get(self.primary_id)
        self.prim_wm_json = self.prim_wm_item.get_data()
    def json_backup(self): #backs up the json to the hardcoded path\
        today = datetime.today().strftime("%Y_%m_%d")
        item_title = self.prim_wm_item.title.lower()
        self.filename = f"{item_title}_{self.primary_id}_{today}.json".replace(":", "-").replace('"', '').replace("|", "_").replace("/", "_").replace("\\", "_")
        self.ostore_path = f'ago_backups/{self.filename}'

        try:
            s3_object = boto_resource.Object(bucket_name, self.ostore_path)
            s3_object.put(
                Body=json.dumps(self.prim_wm_json),
                ContentType='application/json'
            )

            print(f"JSON file {self.filename} has been uploaded to s3://{bucket_name}/{self.ostore_path}")

        except Exception as e:
            print(f"An error occurred: {e}")


#%%
# Backing up
for username in maphub_accounts:

    # only retrieve content from specific folders 
    folders = user.folders
    for folder in folders:
        if folder['title'] == ago_folder_name:
            item_list = []
            for item in user.items(folder['title']):
                if item['type'] in backup_types:
                    item_list.append(item)
    
            for result in item_list:
                in_id = result['id']
                if result['type'] in backup_types:
                    print(f"backing up {in_id}")
                    item = jsonItem(in_id)
                    item.json_backup()


            # # get list of items that match the criteria
            # item_list = []
            # for i in gis.content.search(query="* AND \  owner:" + username, max_items=max_search):
            #     item_list.append(i)

            # # backup item JSONs 
            # for result in item_list:
            #     in_id = result.id
            #     if result.type in backup_types:
            #         print(f"backing up {in_id}")
            #         item = jsonItem(in_id)
            #         item.json_backup()
