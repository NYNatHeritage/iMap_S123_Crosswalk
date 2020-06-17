import requests, json, pickle, urllib, copy, sys, os, getpass, imap_s123_photo, datetime

##
# begin variables
imap_url = 'https://imapdev.natureserve.org/imap/services'
agol_url = 'https://services6.arcgis.com/DZHaqZm9cxOD4CWM/ArcGIS/rest/services/service_eea314a679b549d09bcdf7e1799db7e2/FeatureServer'

searched_area_query = 'iMap3SAId IS NULL'

agol_token = ""

working_directory_file_path = ""

generic_person_id = 16500 # note: this is a placeholder 
# end variables
##

iMapSession = requests.Session()

## initiate a session
#the_password = getpass.getpass()
#login = iMapSession.post('https://imapdev.natureserve.org/imap/j_spring_security_check',{'j_username':'imapinvasives.batch.upload@nynhp.org','j_password':passwordgoeshere})
#login.raise_for_status()
##

## load a previously-saved session
with open('','rb') as thefile:
   iMapSession.cookies.update(pickle.load(thefile))
##


##
# static functions
##

# a function to query data from AGOL REST API
def query_layer(layerId, where, ids_only = None):
    query_url = agol_url + "/" + str(layerId) + "/query"

    agolpayload = {
        "f": "json",
        "where": where,
        "outSr": "4326",
        "outFields": "*",
        "token": agol_token,
        "returnIdsOnly": "true" if ids_only else "false"
    }

    agolr = requests.post(query_url, data=agolpayload)

    return agolr.json()

def id_crosswalk(input_value, cross_walk_values):
    if input_value in cross_walk_values:
        return cross_walk_values[input_value]
    else:
        return None

def true_false_handler(value):
    if value == 'yes':
        return True
    elif value == 'no':
        return False
    else:
        return None

def string_splitter_formatter(string_to_split):
    # formats any comma separated lists into proper format for iMap3 data record
    split_string = str(string_to_split).split(',')

    formatted_data = []
    
    # only attempt the data split if data exists
    if string_to_split:
        for value in split_string:
            formatted_data.append({"id": int(value)})

    return formatted_data

def getStateName(state_id):
    # utility function to get the state name so that it can be used as a lookup in the national list
    with open(working_directory_file_path + "/misc/states.json", 'r') as states_file:
        states = json.load(states_file)
    return states[str(state_id)]

def getJurisdictionSpeciesId(nationalSpeciesListId, state_id):
    state_species_id = None
    nat_species_record = getNatSpecRecord(nationalSpeciesListId)

    state_name = getStateName(state_id)

    for state in nat_species_record['statesTrackedIn']:
        if state['name'] == state_name:
            state_species_id = state['id']
            break

    if (state_species_id is None):
        raise ValueError('unable to find jurisdiction species ID')

    return state_species_id

def getNatSpecRecord(nat_species_list_id):
    # GET the data from the iMap REST API
    iMapDataGet = iMapSession.get(imap_url + '/natSpecList/' + str(nat_species_list_id))

    # check if anything went wrong with the POST request
    iMapDataGet.raise_for_status()

    iMapResponse = iMapDataGet.json()

    # if everything works as expected, the AOI ID of the newly-created feature will print to the console
    return iMapResponse

def getPresentSpeciesRecord(species_id):
    # GET the data from the iMap REST API
    iMapDataGet = iMapSession.get(imap_url + '/presentSpecies/new/' + str(species_id))

    # check if anything went wrong with the POST request
    iMapDataGet.raise_for_status()

    iMapResponse = iMapDataGet.json()

    # if everything works as expected, the AOI ID of the newly-created feature will print to the console
    return iMapResponse

def getNotDetectedSpeciesRecord(species_id):
    # GET the data from the iMap REST API
    iMapDataGet = iMapSession.get(imap_url + '/notDetectedSpecies/new/' + str(species_id))

    # check if anything went wrong with the POST request
    iMapDataGet.raise_for_status()

    iMapResponse = iMapDataGet.json()

    # if everything works as expected, the AOI ID of the newly-created feature will print to the console
    return iMapResponse

# function to write the newly-created iMap 3 searched area ID back to the ArcGIS Online Feature Layer containing the source data
def updateAGOLdata(objectID, imapAOI, agol_url, agol_token):
    # prepare/format the feature changes for ArcGIS Online
    featureslist = [{"attributes": {"objectid" : objectID,"iMap3SAId": imapAOI}}]

    featureslistJSON = json.dumps(featureslist)

    agolurl = '{0}/0/updateFeatures'.format(agol_url)

    # prepare/format the ArcGIS Online request
    agolpayload = {
        "f": "json",
        "token": agol_token,
        "features": featureslistJSON
    }

    # make the request to ArcGIS Online
    agolr = requests.post(agolurl, data=agolpayload)

    # check if anything went wrong with the POST request
    agolr.raise_for_status()

    # get the response
    response = agolr.json()

    # print the results to the console
    print (response)


class records_to_upload:
    def __init__(self, query):
        # get a list of OBJECTIDs to upload matching the input query from the base searched area 
        self.records_to_upload = query_layer(0, query, True)['objectIds']

    def upload_handler(self):
        for objectid in self.records_to_upload:
            record_to_upload = raw_agol_record(objectid)
            new_imap_record = imap_record(record_to_upload)
            new_imap_record.createNewAOI()


class raw_agol_record:
    # to-do: python class composition here?
    def __init__(self, object_id):
        self.searched_area = agol_searched_area(object_id)
        self.presences = agol_presences(self.searched_area.global_id)
        self.not_detected = agol_not_detected(self.searched_area.global_id)
        self.treatments = agol_treatment(self.searched_area.global_id)


class agol_searched_area:
    def __init__(self, searched_area_object_id):
        searched_area_query = "objectid = '" + str(searched_area_object_id) + "'"
        self.raw_response = query_layer(0, searched_area_query)
        self.raw_searched_area = self.raw_response["features"][0]
        self.global_id = self.raw_searched_area["attributes"]["globalid"]
        self.attributes = self.raw_searched_area["attributes"]
        self.geom = self.raw_searched_area["geometry"]


class agol_presences:
    def __init__(self, searched_area_global_id):
        presence_query = "parentglobalid='{0}'".format(searched_area_global_id)
        raw_presences_response = query_layer(5, presence_query)
        self.raw_presences = raw_presences_response["features"]
        self.presences_reformat = []
        self.assemble_presences()

    def assemble_presences(self):
        for presence in self.raw_presences:
            # initialize a dictionary to contain the raw presence record, 
            # corresponding geometry, and present species
            out_presence = {}

            # retrieve any corresponding present species for the presence
            presence_present_species = agol_present_species(presence["attributes"]["globalid"])

            out_presence["presence"] = presence["attributes"]
            out_presence["present_species"] = presence_present_species.present_species_reformat
            out_presence["geometry"] = self.get_presence_geom(presence["attributes"]["presenceGeom"], presence["attributes"]["globalid"])

            self.presences_reformat.append(out_presence)

    def get_presence_geom(self, geom_type, presence_global_id):
        # a dictionary to find proper layer for geom
        geom_layers = {"point": 2, "polygon": 1, "line": 3}

        presence_geom_query = "parentglobalid='{0}'".format(presence_global_id)
        return query_layer(geom_layers[geom_type], presence_geom_query)["features"][0]["geometry"]


class agol_present_species:
    def __init__(self, presence_global_id):
        present_sp_query = "parentglobalid='{0}'".format(presence_global_id)
        self.raw_present_species = query_layer(6, present_sp_query)
        self.present_species_reformat = []

        # reformat present species for ease of use
        for present_sp in self.raw_present_species["features"]:
            self.present_species_reformat.append(present_sp["attributes"])


class agol_not_detected:
    def __init__(self, searched_area_global_id):
        not_detected_query = "parentglobalid='{0}'".format(searched_area_global_id)
        self.raw_not_detected = query_layer(7, not_detected_query)["features"]


class agol_treatment:
    def __init__(self, searched_area_global_id):
        treatment_query = "parentglobalid='{0}'".format(searched_area_global_id)
        self.raw_treatment = query_layer(4, treatment_query)["features"]


# a class to contain an iMap record
class imap_record:
    def __init__(self, agol_record):
        self.agol = agol_record
        self.searched_area = searched_area(self.agol)
        self.not_detected = not_detected(self.agol)
        self.presence_records = presences(self.agol)
        self.treatment_records = treatment(self.agol)
        self.assemble_final_searched_area()

    def assemble_final_searched_area(self):
        self.searched_area.final_searched_area['absence'] = self.not_detected.final_not_detected
        self.searched_area.final_searched_area['presences'] = self.presence_records.final_presences
        self.searched_area.final_searched_area['treatments'] = self.treatment_records.final_treatment

    # uploads a record to iMap
    def createNewAOI(self):
        thePreparedDictToJSON = json.dumps(self.searched_area.final_searched_area)
        
        with open('{0}/out_files/new_searched_area.json'.format(working_directory_file_path), 'w') as logfile:
           logfile.write(thePreparedDictToJSON)

        # url encode the string
        thePreparedJSON = urllib.parse.quote(thePreparedDictToJSON)

        # format the record for iMap REST API POST request
        theRequest = "record=" + thePreparedJSON

        # set headers for proper POST request
        headers = {'content-type': 'application/x-www-form-urlencoded'}

        # POST the data to iMap REST API
        iMapDataPost = iMapSession.post(imap_url + '/aoi/update',data=theRequest,headers=headers)

        print (iMapDataPost.status_code)
        #print (iMapDataPost.text)
        with open('{0}/out_files/new_searched_area.html'.format(working_directory_file_path), 'w') as logfile:
           logfile.write(iMapDataPost.text)

        # check if anything went wrong with the POST request
        iMapDataPost.raise_for_status()

        iMapResponse = iMapDataPost.json()

        # write the new record to a log file for future reference
        # with open('D:\\GIS_Data\\projects\\Invasives\\iMapCrosswalk\\out_files\\imap3_created_records.txt', 'a') as f:
        #     f.write(str(iMapResponse["areaOfInterestId"]) + ',' + str(self.ipmms.assessment_polygon.raw_assessment_record["attributes"]["GlobalID"]) + ',' + datetime.datetime.today().isoformat() + '\n')

        # if everything works as expected, the AOI ID of the newly-created feature will print to the console
        print(iMapResponse["areaOfInterestId"])

        # write newly-created searched area ID back to AGOL layer
        updateAGOLdata(self.agol.searched_area.attributes['objectid'], iMapResponse["areaOfInterestId"], agol_url, agol_token)

        return(iMapResponse)


class searched_area:
    def __init__(self, agol_record):
        self.agol = agol_record
        self.final_searched_area = {}
        self.crosswalk()

    def crosswalk(self):
        # TO-DO: Sampling method ID not POSTing properly!
        searched_area_attributes = self.agol.searched_area.attributes
        thePreparedDict = {
            'areaOfInterestId': None,
            'organization': {'id': searched_area_attributes['OrganizationId']} if searched_area_attributes['OrganizationId'] else None,
            'createdBy': {'id': 16500},
            'leadContactId': None,
            'leadContact': None,
            'comments': searched_area_attributes['searchedAreaComments'],
            'landscapeTypeComments': searched_area_attributes['landscapeTypeComments'],
            'disturbanceComments': searched_area_attributes['disturbanceComments'],
            'deletedInd': False,
            'sensitiveInd': False,
            'dataEntryDate': None,
            'damageToHost': searched_area_attributes['damageToHost'],
            'bulkUploadId': None,
            'permissionReceived': true_false_handler(searched_area_attributes['permissionReceived']),
            'siteAddress': searched_area_attributes['siteAddress'],
            'sourceUniqueId': searched_area_attributes['globalid'],
            'searchDate': searched_area_attributes['ObsDate'],
            'targetTreatmentNeeded': true_false_handler(searched_area_attributes['targetTreatmentNeeded']),
            'searchGoals': None,
            'followUp': true_false_handler(searched_area_attributes['followUp']),
            'ownershipComments': searched_area_attributes['ownershipComments'],
            'crewPaidHours': searched_area_attributes['crewPaidHours'],
            'crewVolunteerHours': searched_area_attributes['crewVolunteerHours'],
            'siteName': searched_area_attributes['siteName'],
            'crewComments': searched_area_attributes['crewComments'],
            'crewVolunteerNum': searched_area_attributes['crewVolunteerNum'],
            'crewNumPaid': searched_area_attributes['crewNumPaid'],
            'airTemperature': searched_area_attributes['airTemperature'],
            'waterTemperature': searched_area_attributes['waterTemperature'],
            'weatherComments': searched_area_attributes['weatherComments'],
            'windSpeed': searched_area_attributes['windSpeed'],
            'survey123Version': None,
            'modifiedDate': None,
            'modifiedBy': None,
            'samplingDetails': searched_area_attributes['samplingDetails'],
            'searchedAreaPostTreatment': None,
            'searchedAreaMaps': [],
            'treatmentsInSearchedArea': [],
            'searchedAreaAquatic': None,
            'areaOfInterestPolygon': {'shape': {'rings': self.agol.searched_area.geom['rings'], 'spatialReference': self.agol.searched_area.raw_response['spatialReference']}},
            'photos': [],
            'presences': [],
            'presentSpeciesIds': [],
            'absence': None,
            'notDetectedSpeciesIds': [],
            'treatments': [],
            'treatmentIds': [],
            'jhostSpecies': [],
            'jownerships': string_splitter_formatter(searched_area_attributes['jownerships']),
            'dsurveyTypeId': None,
            'dcloudCoverId': searched_area_attributes['dcloudCoverId'],
            'dnativeVegetationDistributionId': searched_area_attributes['dnativeVegetationDistributionId'],
            'dpresenceDeterminationMethodId': None,
            'lazy': False,
            'dstateId': int(searched_area_attributes['stateId']),
            'dremovedReasonId': None,
            'dsiteDisturbanceSeverityId': searched_area_attributes['dsiteDisturbanceSeverityId'],
            'jwaterBodyTypes': [],
            'dsiteDisturbanceTypeId': searched_area_attributes['dsiteDisturbanceTypeId'],
            'dlandscapeTypeId': searched_area_attributes['dlandscapeTypeId'],
            'dairTemperatureUnitId': searched_area_attributes['dairTemperatureUnitId'],
            'dwindDirectionId': searched_area_attributes['dwindDirectionId'],
            'jsearchFocusAreasAquatic': [],
            'dwindSpeedUnitId': searched_area_attributes['dwindSpeedUnitId'],
            'jsearchFocusAreasTerrestrial': [],
            'dwaterTemperatureUnitId': searched_area_attributes['dwaterTemperatureUnitId'],
            'jsamplingMethods': []
        }
        self.final_searched_area = thePreparedDict


class presences:
    def __init__(self, agol_record):
        self.agol = agol_record
        self.final_presences = []
        self.crosswalk()

    def crosswalk(self):
        if self.agol.presences.presences_reformat:
            for presence in self.agol.presences.presences_reformat:
                # a list to store the output of the present species records
                final_present_species = []
                
                timeLengthSearchedSum = 0

                for present_species in presence['present_species']:
                    state_species_id = getJurisdictionSpeciesId(present_species['SppID'], self.agol.searched_area.attributes['stateId'])
                    new_present_species_record = getPresentSpeciesRecord(state_species_id)

                    # add to timeLengthSeachedSum for this Presence
                    timeLengthSearchedSum += present_species['timeLengthSearched'] if present_species['timeLengthSearched'] else 0 

                    new_present_species = {
                        'presentSpeciesId': None, 
                        'presenceId': None, 
                        'nationalSpeciesList': new_present_species_record['nationalSpeciesList'], 
                        'stateSpeciesList': new_present_species_record['stateSpeciesList'], 
                        'speciesVerifiedBy': None,
                        'statusChangedBy': None,
                        'confirmedInd': False,
                        'confirmingComments': None,
                        'comments': present_species['presenceComments'],
                        'adminComments': None,
                        'statusChangedDate': None,
                        'sourceUniqueId': present_species['globalid'],
                        'significantRecord': False,
                        'suspiciousDistanceInd': False,
                        'numberFound': present_species['numberFound'],
                        'sourceRecordUrl': None,
                        'sensitiveInd': False,
                        'invasiveImpact': present_species['invasiveImpact'],
                        'repositoryInfo': None,
                        'infestedArea': None,
                        'biocontrolSpeciesFoundComments': present_species['biocontrolSpeciesFoundComments'],
                        'modifiedDate': None,
                        'modifiedBy': None,
                        'uuid': None,
                        'photos': [],
                        'underTreatmentInd': False,
                        'confirmer': True,
                        'isAnyPartOfRecordConfidential': False,
                        'deleted': False,
                        'dfollowUpId': None,
                        'jspeciesIdMethods': [],
                        'dbioagentSpeciesId': present_species['dbioagentSpeciesId'],
                        'devaluationTypeId': present_species['devaluationTypeId'],
                        'dremovedReasonId': None,
                        'taggedProjects': [],
                        'psPlant': {
                            'presentSpeciesId': None,
                            'percentCover': present_species['percentCover'],
                            'intentionalPlantingInd': true_false_handler(present_species['intentionalPlantingInd']),
                            'dcoverClassId': present_species['dcoverClassId'],
                            'jphenologies': string_splitter_formatter(present_species['jphenologies']),
                            'dplantDistributionId': present_species['dplantDistributionId'],
                            'dwoodyPlantMaturityId': present_species['dwoodyPlantMaturityId']
                        }, 
                        'psAnimal': {
                            'presentSpeciesId': None,
                            'foundAliveInd': true_false_handler(present_species['foundAliveInd']),
                            'jinvasiveEvidences': string_splitter_formatter(present_species['jinvasiveEvidences']),
                            'danimalDistributionId': present_species['danimalDistributionId']
                        },
                        'lazy': False,
                        'psAnimalVertebrate': {
                            'presentSpeciesId': None,
                            'juvenileCount': present_species['juvenileCount'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 1 else None,
                            'adultCount': present_species['adultCountOther'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 1 else None,
                            'maleCount': present_species['maleCount'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 1 else None,
                            'femaleCount': present_species['femaleCount'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 1 else None,
                            'animalTraitComments': present_species['animalTraitComments'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 1 else None,
                            'janimalLocationUses': string_splitter_formatter(present_species['janimalLocationUsesOther'])  if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 1 else []
                        },
                        'psAnimalVertebrateAquatic': None,
                        'psAnimalOtherInvertebrate': {
                            'presentSpeciesId': None,
                            'juvenileCount': present_species['juvenileCount'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 3 else None,
                            'adultCount': present_species['adultCountOther'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 3 else None,
                            'maleCount': present_species['maleCount'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 3 else None,
                            'femaleCount': present_species['femaleCount'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 3 else None,
                            'animalTraitComments': present_species['animalTraitComments'] if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 3 else None,
                            'janimalLocationUses': string_splitter_formatter(present_species['janimalLocationUsesOther'])  if new_present_species_record['nationalSpeciesList']['dspeciesTypeId'] == 3 else []
                        },
                        'psAnimalInsect':{
                            'presentSpeciesId': None,
                            'infestedVegetationSpecies': None,
                            'eggCount': present_species['eggCount'],
                            'larvaCount': present_species['larvaCount'],
                            'plantsAffectedCount': present_species['plantsAffectedCount'],
                            'adultCount': present_species['adultCount'],
                            'jinsectLocationFounds': string_splitter_formatter(present_species['jinsectLocationFounds']),
                            'jinsectLifeStages': string_splitter_formatter(present_species['jinsectLifeStages']),
                            'dinsectInfestationSeverityId': present_species['InsectInfestSev'],
                            'janimalLocationUses': string_splitter_formatter(present_species['janimalLocationUses'])
                        },
                        'psMicroOrganism': None
                    }

                    # if the user is an annonymous AGOL user, add the person name and email into admin comments
                    if self.agol.searched_area.attributes['personName'] or self.agol.searched_area.attributes['personEmail']:
                        new_present_species['adminComments'] = 'Submitter Name: {0}\nSubmitter Email Address: {1}'.format(self.agol.searched_area.attributes['personName'], self.agol.searched_area.attributes['personEmail'])

                    # check for any photos
                    new_present_species['photos'] = imap_s123_photo.agol_imap_photo_handler(agol_url, 6, present_species['objectid'], iMapSession, imap_url, agol_token)

                    final_present_species.append(new_present_species)

                new_presence_record = {
                    'areaOfInterestId': None,
                    'presenceId': None,
                    'speciesList': final_present_species,
                    'observer': {'id': self.agol.searched_area.attributes['iMapPersonID'] if self.agol.searched_area.attributes['iMapPersonID'] else generic_person_id},
                    'ismas': [],
                    'timeLengthSearched': (timeLengthSearchedSum * 60) if timeLengthSearchedSum else None,
                    'states': [],
                    'hydrobasins': [],
                    'dapproximateToId': None,
                    'approximationNotes': None,
                    'areaOfInterest': None,
                    'presencePoint': {'shape': {'x': presence['geometry']['x'], 'y': presence['geometry']['y'], 'spatialReference': self.agol.searched_area.raw_response['spatialReference']}} if presence['presence']['presenceGeom'] == 'point' else None,
                    'usgsTopos': [],
                    'modifiedBy': None,
                    'lazy': False,
                    'imap2Id': None,
                    'conservationLands': [],
                    'deleted': False,
                    'bufferDistance': None,
                    'presencePolygon': {'shape': {'rings': presence['geometry']['rings'], 'spatialReference': self.agol.searched_area.raw_response['spatialReference']}} if presence['presence']['presenceGeom'] == 'polygon' else None,
                    'observationDate': self.agol.searched_area.attributes['ObsDate'],
                    'createdBy': {'id': 16500},
                    'createdDate': None,
                    'counties': [],
                    'dremovedReasonId': None,
                    'ddataEntryMethodId': 3,
                    'countries': [],
                    'approximateInd': False,
                    'presenceLine': {'shape': {'paths': presence['geometry']['paths'], 'spatialReference': self.agol.searched_area.raw_response['spatialReference']}} if presence['presence']['presenceGeom'] == 'line' else None,
                    'waterbodies': [],
                    'modifiedDate': None
                }

                self.final_presences.append(new_presence_record)


class not_detected:
    def __init__(self, agol_record):
        self.agol = agol_record
        self.final_not_detected = None
        self.crosswalk()

    def crosswalk(self):
        # prepare a list of all not detected species
        not_detected_species = []

        if self.agol.not_detected.raw_not_detected:
            # assemble all not detected species
            for not_detected_record in self.agol.not_detected.raw_not_detected:
                # get a new species record
                not_detected_attributes = not_detected_record['attributes']
                state_species_id = getJurisdictionSpeciesId(not_detected_attributes['notDetectedSpecies'], self.agol.searched_area.attributes['stateId'])
                not_detected_species_record = getNotDetectedSpeciesRecord(state_species_id)

                new_not_detected_species = {
                    'absentSpeciesId': None,
                    'absenceId': None,
                    'nationalSpeciesList': not_detected_species_record['nationalSpeciesList'],
                    'stateSpeciesList': not_detected_species_record['stateSpeciesList'],
                    'statusChangedById': None,
                    'statusChangedBy': None,
                    'comments': not_detected_attributes['notDetectedComments'],
                    'adminComments': None,
                    'statusChangedDate': None,
                    'sourceUniqueId': not_detected_attributes['globalid'],
                    'sensitiveInd': False,
                    'presumedEliminatedInd': False,
                    'modifiedDate': None,
                    'modifiedById': None,
                    'modifiedBy': None,
                    'uuid': None,
                    'photos': [],
                    'confirmer': True,
                    'lazy': False,
                    'deleted': False,
                    'dremovedReasonId': None,
                    'dabsenceConfidenceId': None,
                    'dabsenceReasonId': not_detected_attributes['dabsenceReasonId'],
                    'taggedProjects': []
                }

                # if the user is an annonymous AGOL user, add the person name and email into admin comments
                if self.agol.searched_area.attributes['personName'] or self.agol.searched_area.attributes['personEmail']:
                    new_not_detected_species['adminComments'] = 'Submitter Name: {0}\nSubmitter Email Address: {1}'.format(self.agol.searched_area.attributes['personName'], self.agol.searched_area.attributes['personEmail'])

                # check for any not detected photos
                new_not_detected_species['photos'] = imap_s123_photo.agol_imap_photo_handler(agol_url, 7, not_detected_attributes['objectid'], iMapSession, imap_url, agol_token)

                not_detected_species.append(new_not_detected_species)

            # construct the not detected record
            new_not_detected = {
                'absenceId': None,
                'areaOfInterest': None,
                'areaOfInterestId': None,
                'observer': {"id": self.agol.searched_area.attributes['iMapPersonID'] if self.agol.searched_area.attributes['iMapPersonID'] else generic_person_id},
                'createdBy': {'id': 16500},
                'observationDate': self.agol.searched_area.attributes['ObsDate'],
                'timeLengthSearched': None,
                'modifiedDate': None,
                'modifiedBy': None,
                'absencePolygon': {'shape': {'rings': self.agol.searched_area.geom['rings'], 'spatialReference': self.agol.searched_area.raw_response['spatialReference']}},
                'speciesList': not_detected_species,
                'lazy': False,
                'deleted': False,
                'createdDate': None,
                'counties': [],
                'waterbodies': [],
                'countries': [],
                'ismas': [],
                'hydrobasins': [],
                'states': [],
                'usgsTopos': [],
                'imap2Id': None,
                'dremovedReasonId': None,
                'ddataEntryMethodId': 3,
                'conservationLands': []
            }

            self.final_not_detected = new_not_detected


# iMap3 treatments class
class treatment:
    def __init__(self, agol_record):
        self.agol = agol_record
        self.final_treatment = []
        self.crosswalk()

    def crosswalk(self):
        # this method probably does too much and should be split out
        if self.agol.treatments.raw_treatment:
            for treatment in self.agol.treatments.raw_treatment:
                # isolate the treatment attributes
                treatment_attributes = treatment['attributes']
                # get the state species ID value for the treatment target species
                state_species_id = getJurisdictionSpeciesId(treatment_attributes['treatmentTargetSpecies'], self.agol.searched_area.attributes['stateId'])

                # initialize a base treatment record
                new_treatment = {
                    'treatmentId': None,
                    'areaOfInterest': None,
                    'localContactOrganization': None,
                    'organization': {'id': self.agol.searched_area.attributes['OrganizationId']} if self.agol.searched_area.attributes['OrganizationId'] else None,
                    'modifiedBy': None,
                    'createdBy': {
                        'id': 16500
                    },
                    'leadContact': {'id': self.agol.searched_area.attributes['iMapPersonID'] if self.agol.searched_area.attributes['iMapPersonID'] else generic_person_id},
                    'sensitiveInd': False,
                    'survey123Version': None,
                    'adminComments': None,
                    'sourceUniqueId': treatment_attributes['globalid'],
                    'bulkUploadId': None,
                    'localContactName': None,
                    'permitComments': treatment_attributes['permitComments'],
                    'rareSpeciesPrecautions': treatment_attributes['rareSpeciesPrecautions'],
                    'targetSpeciesComments': None,
                    'comments': treatment_attributes['TrtmntComments'],
                    'createdDate': None,
                    'dateBegin': treatment_attributes['dateBegin'],
                    'dateEnd': treatment_attributes['dateEnd'],
                    'treatmentTypeComments': None,
                    'modifiedDate': None,
                    'taggedProjects': [],
                    'treatmentChemicalsUsed': [],
                    'treatmentTargetSpecies': [{'jurisdictionSpecies': {'id': state_species_id}}],
                    'treatmentPhysical': None,
                    'treatmentBiological': None,
                    'treatmentPolygon': {'shape': {'rings': treatment['geometry']['rings'], 'spatialReference': self.agol.searched_area.raw_response['spatialReference']}},
                    'treatmentChemical': None,
                    'treatmentPhotos': [],
                    'treatedPresentSpecies': [],
                    'dtreatmentTypeId': treatment_attributes['dtreatmentTypeId'],
                    'jmechanicalMethods': [],
                    'jbarrierMethods': [],
                    'jchemicalApplicationMethods': [],
                    'jgrazingAnimalTypes': [],
                    'jphysicalTreatmentMethods': [],
                    'jtreatmentGoals': string_splitter_formatter(treatment_attributes['jtreatmentGoals']),
                    'jdisposalMethods': [],
                    'dstateId': self.agol.searched_area.attributes['stateId'],
                    'deleted': False,
                    'lazy': False,
                    'dtreatmentIterationId': treatment_attributes['dtreatmentIterationId'],
                    'imap2Id': None
                    }

                # if the treatment type is physical, specify the correct parameters in the main treatment record
                if treatment_attributes['dtreatmentTypeId'] == 1:
                    new_treatment['treatmentPhysical'] = {
                        'treatmentId': None,
                        'fireDatabaseUsed': treatment_attributes['fireDatabaseUsed'],
                        'fireDatabaseRecordUrl': treatment_attributes['fireDatabaseRecordUrl'],
                        'barrierInstallationMethod': treatment_attributes['barrierInstallationMethod'],
                        'barrierNumDays': treatment_attributes['barrierNumDays'],
                        'grazingBreedOfAnimal': treatment_attributes['grazingBreedOfAnimal'],
                        'grazingNumDays': treatment_attributes['grazingNumDays'],
                        'grazingNumAnimals': treatment_attributes['grazingNumAnimals'],
                        'numAnimalsKilledTrapped': treatment_attributes['numAnimalsKilledTrapped'],
                        'otherPhysicalTreatmentMethod': None,
                        'comments': treatment_attributes['treatmentPhysicalComments']
                    }

                    new_treatment['jmechanicalMethods'] = string_splitter_formatter(treatment_attributes['jmechanicalMethods'])
                    new_treatment['jdisposalMethods'] = string_splitter_formatter(treatment_attributes['jdisposalMethods'])
                    new_treatment['jbarrierMethods'] = string_splitter_formatter(treatment_attributes['jbarrierMethods'])
                    new_treatment['jgrazingAnimalTypes'] = string_splitter_formatter(treatment_attributes['jgrazingAnimalTypes'])
                    new_treatment['jphysicalTreatmentMethods'] = string_splitter_formatter(treatment_attributes['jphysicalTreatmentMethods'])

                # if the treatment type is chemical, specify the correct parameters in the main treatment record
                if treatment_attributes['dtreatmentTypeId'] == 2:
                    new_treatment['treatmentChemical'] = {
                        'treatmentId': None,
                        'applicatorName': treatment_attributes['applicatorName'],
                        'surfactant': treatment_attributes['surfactant'],
                        'adjuvant': treatment_attributes['adjuvant'],
                        'quantityUsedTotalMixture': treatment_attributes['quantityUsedTotalMixture'],
                        'sensitiveAreaInd': None,
                        'address': treatment_attributes['address'],
                        'city': treatment_attributes['city'],
                        'zipcode': treatment_attributes['zipcode'],
                        'rainfallPotential': None,
                        'surplusQuantityAndDisposal': None,
                        'spillResponseAndCleanup': None,
                        'comments': treatment_attributes['treatmentChemicalComments'],
                        'dvolumeUnitId': treatment_attributes['dvolumeUnitIdTotalQuant']
                    }

                    # if any of the chemical used fields are completed, initialize a chemical used record
                    if (treatment_attributes['brandName'] or treatment_attributes['epaRegistrationNum'] or treatment_attributes['concentrationOfProduct'] or treatment_attributes['concentrationOfApplication'] or treatment_attributes['quantityUsedUnmixed'] or treatment_attributes['dvolumeUnitId'] or treatment_attributes['jactiveIngredient']):
                        new_chemical_used = {'treatmentChemicalUsedId': 0, 'treatmentId': 0, 'brandName': treatment_attributes['brandName'], 'epaRegistrationNum': treatment_attributes['epaRegistrationNum'], 'concentrationOfProduct': treatment_attributes['concentrationOfProduct'], 'concentrationOfApplication': treatment_attributes['concentrationOfApplication'], 'quantityUsedUnmixed': treatment_attributes['quantityUsedUnmixed'], 'dvolumeUnitId': treatment_attributes['dvolumeUnitId'], 'jactiveIngredients': string_splitter_formatter(treatment_attributes['jactiveIngredient'])}
                        new_treatment['treatmentChemicalsUsed'].append(new_chemical_used)

                    # if any of the second chemical used fields are completed, initialize a chemical used record
                    if (treatment_attributes['brandName2'] or treatment_attributes['epaRegistrationNum2'] or treatment_attributes['concentrationOfProduct2'] or treatment_attributes['concentrationOfApplication2'] or treatment_attributes['quantityUsedUnmixed2'] or treatment_attributes['dvolumeUnitId2'] or treatment_attributes['jactiveIngredient2']):
                        new_chemical_used_2 = {'treatmentChemicalUsedId': 0, 'treatmentId': 0, 'brandName': treatment_attributes['brandName2'], 'epaRegistrationNum': treatment_attributes['epaRegistrationNum2'], 'concentrationOfProduct': treatment_attributes['concentrationOfProduct2'], 'concentrationOfApplication': treatment_attributes['concentrationOfApplication2'], 'quantityUsedUnmixed': treatment_attributes['quantityUsedUnmixed2'], 'dvolumeUnitId': treatment_attributes['dvolumeUnitId2'], 'jactiveIngredients': string_splitter_formatter(treatment_attributes['jactiveIngredient2'])}
                        new_treatment['treatmentChemicalsUsed'].append(new_chemical_used_2)

                    new_treatment['jchemicalApplicationMethods'] = string_splitter_formatter(treatment_attributes['jchemicalApplicationMethods'])

                if treatment_attributes['dtreatmentTypeId'] == 3:
                    new_treatment['treatmentBiological'] = {
                        'treatmentId': None,
                        'bioagentGenoType': treatment_attributes['bioagentGenoType'],
                        'bioagentReleasedNum': treatment_attributes['bioagentReleasedNum'],
                        'bioagentComments': treatment_attributes['bioagentComments'],
                        'biocontrolSourceReceiptDetails': treatment_attributes['biocontrolSourceReceiptDetails'],
                        'dbioagentReleaseStageId': treatment_attributes['dbioagentReleaseStageId'],
                        'dbioagentSpeciesId': treatment_attributes['dbioagentSpeciesIdTrt']
                    }

                                # if the user is an annonymous AGOL user, add the person name and email into admin comments
                
                if self.agol.searched_area.attributes['personName'] or self.agol.searched_area.attributes['personEmail']:
                    new_treatment['adminComments'] = 'Submitter Name: {0}\nSubmitter Email Address: {1}'.format(self.agol.searched_area.attributes['personName'], self.agol.searched_area.attributes['personEmail'])

                self.final_treatment.append(new_treatment)


uploader = records_to_upload(searched_area_query)
uploader.upload_handler()
