import requests, json, urllib.parse

def upload_photo(file_name, in_file, file_format, session, imap_url):
    files = {'file': (file_name, in_file, file_format)}

    imap_img_url = '{0}/image'.format(imap_url)

    # POST the data to iMap REST API
    iMapDataPost = session.post(imap_img_url,files=files)

    # raise an error if an unexpected response is returned from iMap
    iMapDataPost.raise_for_status()

    # if the request was successful, return the resulting JSON
    if iMapDataPost.status_code == 200:
        response_json = iMapDataPost.json()
        return response_json
    else:
        raise ValueError("200 was not returned from iMap upon photo upload!")

def get_attach_data(base_url, layerId, objectId, agol_token):
    request_url = '{0}/{1}/queryAttachments?objectIds={2}&returnUrl=true&f=json&token={3}'.format(base_url, layerId, objectId, agol_token)
    the_photos = requests.get(request_url)
    the_photos.raise_for_status() 
    the_photos_json = the_photos.json()
    final_urls = the_photos_json['attachmentGroups'][0]['attachmentInfos'] if (len(the_photos_json['attachmentGroups']) > 0) else []
    return final_urls

def get_photo(url, agol_token):
    raw_photo = requests.get(url + "?token=" + agol_token)
    return raw_photo.content

def imap_photo_format_handler(uploaded_photos):
    imap_formatted_photos = []
    
    for photo in uploaded_photos:
        imap_formatted_photos.append({"presentSpeciesPhotoId":None,"presentSpeciesId":None,"photoUrl":photo['url'],"photoCredit":None})

    return imap_formatted_photos

def agol_imap_photo_handler(base_url, layerId, objectId, session, imap_url, agol_token):
    #initialize a list to store the uploaded photos to iMap
    imap_photos = []

    # get the attachments list from AGOL for the taget OBJECTID
    photos = get_attach_data(base_url, layerId, objectId, agol_token)

    # attempt to download the raw photo and upload it to iMap
    for photo in photos:
        # download the individual photo from AGOL
        downloaded_photo = get_photo(photo['url'], agol_token)
        # upload the photo to the iMap and return its temporary URL
        uploaded_photo = upload_photo(photo['name'], downloaded_photo, photo['contentType'], session, imap_url)
        # append the new iMap photo to the output list
        imap_photos.append(uploaded_photo)

    # return formatted list of photos ready for association with imap records
    return imap_photo_format_handler(imap_photos)
