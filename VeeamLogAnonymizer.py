#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = "Julien Mousqueton"
__copyright__ = "Copyright 2025, Julien Mousqueton"
__version__ = "1.2"

# Import necessary modules
import re
import random
import string
import sys
import os
import argparse
import logging
import json
import shutil
import time
import datetime
import glob


# Configure logging
logging.basicConfig(
    format='%(asctime)s,%(msecs)d %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO
)

# Define custom logging functions
def stdlog(msg):
    '''Standard info logging'''
    logging.info(msg)

def dbglog(msg):
    '''Debug logging'''
    logging.debug(msg)

def errlog(msg):
    '''Error logging'''
    logging.error(msg)

def generate_random_string(length=12):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def replace_string_in_file(input, output, old_value, new_value):
    with open(input, 'r') as file:
        content = file.read()
    pattern = re.compile(re.escape(old_value), re.IGNORECASE)
    content = pattern.sub(lambda match: new_value if match.group(0).islower() else new_value.upper(), content)
    with open(output, 'w') as file:
        file.write(content)

def check_log_contains_line(input_file, line_to_check):
    with open(input_file, 'r') as file:
        for line in file:
            if line_to_check in line:
                return True
    return False

def get_object_from_location(location):
    components = location.split('\\')
    return components

def get_element_from_fqdn(fqdn):
    result = fqdn.split('.')
    return result   

def is_fqdn(string):
    # Regular expression patterns to match FQDN 
    fqdn_pattern = r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(fqdn_pattern, string):
        return True
    else:
        return False
    
def is_IP(string):
    # Regular expression patterns to match  IP addresses
    ip_pattern = r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'

    if re.match(ip_pattern, string):
        return True
    else:
        return False

def anonymized_IPv4(ip):
    ip_address = ip.split(".")
    ip_address[0] = "**"
    ip_address[1] = "**"
    masked_ip = ".".join(ip_address)
    return masked_ip


def process_IP(input_file, output_file):
    # Define a regular expression pattern to match IP addresses
    ip_pattern = r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b(?!])"

    # Read the file
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.read()

    # Find all IP addresses in the content using regex
    ip_addresses = re.findall(ip_pattern, content)

    # Replace the first two numbers with "*"
    for ip in ip_addresses:
        # Exception for VMware vSphere version 
        if not ip.startswith(('7.', '8.')):
            content = content.replace(ip, anonymized_IPv4(ip))

    ### another pattern :( 
    ip_pattern = r'\[::ffff:([\d.]+)\]'
    ip_addresses = re.findall(ip_pattern, content)
    for ip in ip_addresses:
        # Exception for VMware vSphere version 
        if not ip.startswith(('7.', '8.')):
            content = content.replace(ip, anonymized_IPv4(ip))
    # Write the modified content back to the file
    with open(output_file, 'w') as file:
        file.write(content)
    
def find_pattern(pattern_key,log_file_path,):
    try:
        with open("patterns.json", "r") as patterns_file:
            patterns_dict = json.load(patterns_file)
        
        pattern = patterns_dict.get(pattern_key)
        if not pattern:
            return f"Pattern key '{pattern_key}' not found in patterns.json."

        with open(log_file_path, "r", encoding='utf-8', errors='ignore') as log_file:
            log_content = log_file.read()

        matches = re.findall(pattern, log_content)
        matches = list(set(matches))

        if matches:
            return matches
        else:
            return None
    except FileNotFoundError:
        return f"Error: File '{log_file_path}' not found."
    except Exception as e:
        return f"An error occurred: {str(e)}"


def extract_domain(email):
    # Utilisation d'une expression régulière pour extraire le nom de domaine
    match = re.search(r'@([\w.-]+)', email)
    
    # Si une correspondance est trouvée, renvoie le nom de domaine, sinon renvoie None
    if match:
        return match.group(1)
    else:
        return None
    

def update_json_file(object_name, name_of_value, value, output_file):
    # Try to read the existing JSON data if the file exists
    try:
        with open(output_file, 'r') as json_file:
            existing_data = json.load(json_file)
    except FileNotFoundError:
        # pass  # If the file doesn't exist, ignore the error
        existing_data = {}

    # Update the existing data or create a new entry
    if object_name in existing_data:
        # Check if the name_of_value already exists in the list
        found = False
        for item in existing_data[object_name]:
            if name_of_value in item:
                item[name_of_value] = str(value)  # Update the existing value
                found = True
                break
        if not found:
            existing_data[object_name].append({name_of_value: str(value)})  # Add a new entry
    else:
        existing_data[object_name] = [{name_of_value: str(value)}]

    # Write the updated data to the file
    with open(output_file, 'w') as json_file:
        json.dump(existing_data, json_file, indent=4)



def main():
    parser = argparse.ArgumentParser(description="Anonymize your Veeam Backup & Replication logs.")
    parser.add_argument("-i", "--input", dest="input_file", help="Input log file")
    parser.add_argument("-d", "--directory", dest="input_directory", help="Input directory containing log files")
    parser.add_argument("-o", "--output", dest="output_directory", required=True, help="Output directory for processed log files")
    parser.add_argument("-f", "--force", action="store_true", help="Force overwrite if output files exist or force the creation of output directory if not exists")
    parser.add_argument("-m","--mapping", action="store_true", help="Display the mapping table of anonymized data")
    parser.add_argument("-v", "--verbose", action="store_true", help="Display processing files and other information")
    parser.add_argument("-D", "--dictionary", action="store_true", help="output a JSON file with the dictionary of anonymized data")

    if not os.path.exists('patterns.json'):
        errlog("Error: patterns.json not found.")
        sys.exit(1)

    args = parser.parse_args()

    input_files=[]

    verbose = args.verbose 

    if args.input_file:
        input_files.append(args.input_file)
    elif args.input_directory:
        input_directory = args.input_directory
        if not os.path.isdir(input_directory):
            errlog('Error : '+ input_directory +' is not a directory')
            sys.exit(1)
        if not os.path.exists(input_directory):
            errlog('Error: Input directory ' + input_directory + ' does not exist.')
            sys.exit(1)
         # Use os.walk to find all .log files recursively
        for root, _, files in os.walk(input_directory):
            for filename in files:
                if filename.endswith(".log"):
                    input_files.append(os.path.join(root, filename))

    else:
        errlog('Error: You must specify either -i or -d.')
        sys.exit(1)
        
    output_directory = args.output_directory

    # Specify the pattern to match files with a similar format
    filename_pattern = 'VeeamAnonymizer-*.json'

    # Create the full path pattern by joining the directory and filename pattern
    file_pattern = os.path.join(output_directory, filename_pattern)
    # Use glob to find files matching the pattern
    matching_files = glob.glob(file_pattern)

    # Check if any matching files were found
    if matching_files:
        stdlog("ATTENTION : An old VeeamAnonymizer dictionnary exists in the output directory")

    # Init list 
    VeeamServer = False
    
    VeeamUserList = []
    User_set = set()
    
    SMTPServerList = []
    SMTPServer_set = set()
    
    vCenterList = []
    vCenter_set = set()

    DomainList = []
    Domain_set = set()

    LocationList = []
    Location_set = set() 

    EmailList = []
    Email_set = set()
    
    ESXiList = []
    ESXi_set = set()

    nbfile = 0

    stdlog('Collecting information')
    for input_file in input_files:
        nbfile += 1
        filename = os.path.basename(input_file)
        
        dbglog('*** ' +  filename)
        
        output_file = os.path.join(output_directory, filename)
        
        if os.path.exists(output_file) and not args.force:
            errlog(f'Error: Output file {output_file} already exists. Use -f or --force to overwrite.')
            sys.exit(1)
        
        ### SMTP 
        SMTPServers = find_pattern('SMTPServer',input_file)
        try:
            for SMTPServer in SMTPServers:
                if SMTPServer in SMTPServer_set:
                    continue
                SMTPServer_set.add(SMTPServer)
                if is_fqdn(SMTPServer):
                    RandomSMTP = str(generate_random_string())
                    Domain = '.'.join(get_element_from_fqdn(SMTPServer)[1:])
                    if Domain not in Domain_set:
                        Domain_set.add(Domain)
                        element = (Domain, RandomDomain)
                        DomainList.append(element)
                else:
                    RandomSMTP = anonymized_IPv4(SMTPServer)
                element = (SMTPServer, RandomSMTP)
                SMTPServerList.append(element)
        except:
            pass

        if not VeeamServer:
            try: 
                VeeamServer = str(find_pattern('VeeamServer',input_file)[0])
                RandomVeeamServer = str(generate_random_string())
            except:
                pass

        ### Veeam User 
        VeeamUsers = find_pattern('VeeamUser',input_file)
        try: 
            for VeeamUser in VeeamUsers:
                tmpUser = VeeamUser.split("\\")[1]
                tmpRandom = str(generate_random_string())
                if tmpUser in User_set:
                    continue
                User_set.add(tmpUser)  # Add the unique tmpUser value to the set
                element = (tmpUser, tmpRandom)
                VeeamUserList.append(element)
        except:
            pass
        
        ### vCenter Server 
        vCenters = find_pattern('vCenter',input_file)
        try: 
            for vCenter in vCenters:
                if len(vCenter) == 0:
                    continue 
                if is_fqdn(vCenter):
                    RandomDomain = str(generate_random_string())
                    Domain = '.'.join(get_element_from_fqdn(vCenter)[1:])
                    if Domain not in Domain_set:
                        Domain_set.add(Domain)
                        element = (Domain, RandomDomain)
                        DomainList.append(element)
                    vCenter = get_element_from_fqdn(vCenter)[0]
                    RandomvCenter = str(generate_random_string())
                else:
                    RandomvCenter= anonymized_IPv4(vCenter)
                if vCenter in vCenter_set:
                    continue
                vCenter_set.add(vCenter)  # Add the unique tmpUser value to the set
                element = (vCenter, RandomvCenter)
                vCenterList.append(element)              
        except:
            pass


        ### Location 
        Locations = find_pattern('Location', input_file)
        try: 
            for Location in Locations:
                split_data = Location.split('\\')
                # Print all parts except the first and last ones
                for part in split_data[1:-1]:
                    RandomLocation = str(generate_random_string())
                    if part not in Location_set:
                        Location_set.add(part)
                        element = (part, RandomLocation)
                        LocationList.append(element)                  
        except:
           pass

        #ESXi Server 
        ESXiServers = find_pattern('ESXiServer',input_file)
        try:
            for ESXi in ESXiServers:
                if is_fqdn(ESXi):
                    RandomDomain = str(generate_random_string())
                    Domain = '.'.join(get_element_from_fqdn(ESXi)[1:])
                    if Domain not in Domain_set:
                        Domain_set.add(Domain)
                        element = (Domain, RandomDomain)
                        DomainList.append(element)
                    ESXi = get_element_from_fqdn(ESXi)[0]
                    RandomESXi = str(generate_random_string())
                else:
                    RandomESXi = anonymized_IPv4(ESXi)
                if ESXi in ESXi_set:
                    continue
                ESXi_set.add(ESXi)
                element = (ESXi, RandomESXi)
                ESXiList.append(element) 
        except:
            pass

        ### email 
        Emails = find_pattern('Email', input_file)
        try: 
            for Email in Emails:
                RandomEmail = str(generate_random_string())
                Domain = extract_domain(Email)
                if Domain and Domain not in Domain_set:
                        Domain_set.add(Domain)
                        RandomDomain = str(generate_random_string())
                        element = (Domain, RandomDomain)
                        DomainList.append(element)
                if Email in Email_set:
                    continue 
                Email_set.add(Email)
                RandomEmail = RandomEmail + '@' + RandomDomain
                element = (Email, RandomEmail)
                EmailList.append(element)
        except:
           pass

    # Clean list 
    UniqueVeeamUsers = list(sorted(set(VeeamUserList)))
    UniqueSMTPSevers = list(set(SMTPServerList))
    UniquevCenters   = list(sorted(set(vCenterList)))
    UniqueEmails     = list(set(EmailList))
    UniqueESXi       = list(sorted(set(ESXiList)))
    UniqueLocation   = list(sorted(set(LocationList)))

    ### GET Domain and subdomain 
    try:
        for Domain in DomainList:
            _Original, _Random = Domain
            parts = _Original.split('.')
            if len(parts) > 2:
                main_domain = '.'.join(parts[-2:])
                if main_domain not in Domain_set:
                        Domain_set.add(main_domain)
                        RandomDomain = str(generate_random_string())
                        element = (main_domain, RandomDomain)
                        DomainList.append(element)
    except:
        pass

    UniqueDomains    = list(set(DomainList))


    ## Cleaning ESXi 
    filtered_ESXi = [(original, random) for (original, random) in UniqueESXi if original not in {vc[0] for vc in UniquevCenters}]
    
    if args.dictionary: 
        if not os.path.exists(output_directory) and args.force:
            os.makedirs(output_directory)  
        current_datetime = datetime.datetime.now()
        formatted_datetime = current_datetime.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"VeeamAnonymizer-{formatted_datetime}.json"
        outputdictfile  = output_directory + "/" + filename
        # Add a new entry to the "Vcenter" section
        for data in UniqueVeeamUsers:
                _Original, _Random = data
                update_json_file("VeeamUsers", _Original, _Random, outputdictfile)
        for data in UniqueSMTPSevers:
                _Original, _Random = data
                update_json_file("SMTP Servers", _Original, _Random, outputdictfile)
        for data in UniquevCenters:
                _Original, _Random = data
                update_json_file("vCenter Servers", _Original, _Random, outputdictfile)
        for data in UniqueLocation:
                _Original, _Random = data
                update_json_file("vCenter Location", _Original, _Random, outputdictfile)
        for data in UniqueEmails:
                _Original, _Random = data
                update_json_file("Email address", _Original, _Random, outputdictfile)
        for data in filtered_ESXi: 
                _Original, _Random = data
                update_json_file("ESXi hosts", _Original, _Random, outputdictfile)
        for data in UniqueDomains:
                _Original, _Random = data
                update_json_file("Domain names", _Original, _Random, outputdictfile)
        stdlog('Json file created')


    if args.mapping:
        # Show the mapping 
        ## VEEAM
        try:
            stdlog('* Veeam Server : ' + VeeamServer + ' -> ' + RandomVeeamServer)
        except: 
            pass
        
        ### SMTP
        try:
            for SMTPServer in UniqueSMTPSevers:
                _OriginalSMTP, _RandomSMTP = SMTPServer
                stdlog('* SMTP Server : ' + _OriginalSMTP + ' -> ' + _RandomSMTP)
        except: 
            pass
        
        ### vCenter 
        try:
            for vCenter in UniquevCenters:
                _Original, _Random = vCenter
                stdlog('* vCenter Server : ' + _Original + ' -> ' + _Random)
        except: 
            pass
        # Location 
        try:
            for Location in UniqueLocation:
                _Original, _Random = Location
                stdlog('* vCenter Location : ' + _Original + ' -> ' + _Random)
        except: 
            pass
        ### Domain 
        try:
            for Domain in UniqueDomains:
                _Original, _Random = Domain
                stdlog('* Domain : ' + _Original + ' -> ' + _Random)
        except: 
            pass
        ### Email 
        try:
            for Email in UniqueEmails:
                _Original, _Random = Email
                stdlog('* Email : ' + _Original + ' -> ' + _Random)
        except:
            pass
        
        ### Veeam User Accounts 
        try:
            for VeeamUser in UniqueVeeamUsers:
                _Original, _Random = VeeamUser
                stdlog('* User: ' + _Original + ' -> ' + _Random)
        except: 
            pass

        ### ESXi
        try:
            for ESXi in filtered_ESXi:
                _Original, _Random = ESXi
                stdlog('* ESXi: ' + _Original + ' -> ' + _Random)
        except:
            pass  
       
        
    ###
    # Anonymizing 
    ###

    i = 0 
    ##  UniqueESXi = list(sorted(set(ESXiList)))
    
    stdlog('Processing anonymizing of ' + str(nbfile) + ' file(s) ... ')
    for input_file in input_files:
        filename = os.path.basename(input_file)
        if args.input_file:
            output_file = os.path.join(output_directory, filename)
            full_output_directory = os.path.dirname(output_file)
        else:
            output_file = input_file.replace(args.input_directory,args.output_directory,1)
            full_output_directory = os.path.dirname(output_file)
        
        if not os.path.exists(full_output_directory) and args.force:
            os.makedirs(full_output_directory)  
        
        if verbose:
            i +=  1
            file_size_bytes = os.path.getsize(input_file)
            file_size_megabytes = round(file_size_bytes / (1024 * 1024),2)
            stdlog('- Processing file ['+ str(i) + '/' + str(nbfile) + '] '+ input_file + '(' + str(file_size_megabytes)+ ' Mb)')
        
        try:
            shutil.copy(input_file, output_file)
        except:
            errlog('Fatal Error processing : ' + input_file + ' --> ' + output_file)
            sys.exit(1)

        try:
            replace_string_in_file(output_file,output_file, VeeamServer, RandomVeeamServer)
        except: 
            pass


        try: 
            for ESXi in filtered_ESXi:
                _Original, _Random = ESXi
                dbglog('    + anonymizing ESXi')
                replace_string_in_file(output_file,output_file, _Original, _Random)
        except: 
            pass


        try:
            for Domain in UniqueDomains:
                _Original, _Random = Domain
                dbglog('    + anonymizing Domain')
                replace_string_in_file(output_file,output_file, _Original, _Random)
        except: 
            pass
    
        try:
            for SMTPServer in UniqueSMTPSevers:
                _Original, _Random = SMTPServer
                dbglog('    + anonymizing SMTPServer')
                replace_string_in_file(output_file,output_file, _Original, _Random)
        except: 
            pass

        try:
            for vCenter in UniquevCenters:
                _Original, _Random = vCenter
                dbglog('    + anonymizing vCenter')
                replace_string_in_file(output_file,output_file, _Original, _Random)
        except: 
            pass
    
        try:
            for VeeamUser in UniqueVeeamUsers:
                _Original, _Random = VeeamUser
                dbglog('    + anonymizing VeeamUser')
                replace_string_in_file(output_file,output_file, _Original, _Random)
        except: 
            pass

        try:
            for Email in UniqueEmails:
                _Original, _Random = Email
                dbglog('    + anonymizing Email')
                replace_string_in_file(output_file,output_file, _Original, _Random)
        except:
            pass

        try:
            for Location in UniqueLocation:
                _Original, _Random = Location
                dbglog('    + anonymizing Location')
                replace_string_in_file(output_file,output_file, _Original, _Random)
        except:
            pass   

        # For IPs
        dbglog('    + anonymizing IP Address')
        process_IP(output_file,output_file)
        dbglog('- File ' + input_file + ' processed')
    end_time = time.time()
    elapsed_time = end_time - start_time
    minutes = str(int(elapsed_time // 60))
    seconds = str(int(elapsed_time % 60))
    stdlog('Anonymizng finished in ' + minutes + '  minutes and ' + seconds + ' seconds')

if __name__ == "__main__":
    start_time = time.time()
    print(
    f'''
.-.   .-.,---.  ,---.    .--.                   ,-.    .---.    ,--,              .--.  .-. .-. .---.  .-. .-..-.   .-.        ,-. _____  ,---.  ,---.    
 \ \ / / | .-'  | .-'   / /\ \ |\    /|         | |   / .-. ) .' .'              / /\ \ |  \| |/ .-. ) |  \| | \ \_/ )/|\    /||(|/___  / | .-'  | .-.\   
  \ V /  | `-.  | `-.  / /__\ \|(\  / |         | |   | | |(_)|  |  __          / /__\ \|   | || | |(_)|   | |  \   (_)|(\  / |(_)   / /) | `-.  | `-'/   
   ) /   | .-'  | .-'  |  __  |(_)\/  |         | |   | | | | \  \ ( _)         |  __  || |\  || | | | | |\  |   ) (   (_)\/  || |  / /(_)| .-'  |   (    
   (_)   |  `--.|  `--.| |  |)|| \  / |         | `--.\ `-' /  \  `-) )         | |  |)|| | |)|\ `-' / | | |)|   | |   | \  / || | / /___ |  `--.| |\ \   
         /( __.'/( __.'|_|  (_)| |\/| |         |( __.')---'   )\____/          |_|  (_)/(  (_) )---'  /(  (_)  /(_|   | |\/| |`-'(_____/ /( __.'|_| \)\  
        (__)   (__)            '-'  '-'         (_)   (_)     (__)                     (__)    (_)    (__)     (__)    '-'  '-'          (__) v {__version__}  (__) 
    by Julien Mousqueton (@JMousqueton)
    '''
    )
    main()
