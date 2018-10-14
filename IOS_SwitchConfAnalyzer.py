import re
from collections import defaultdict
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl import Workbook
import tkinter as tk
from tkinter import filedialog


def xl_adjust_column_width(ws):
    for col in ws.columns:
        max_length = 0
        column = col[0].column # Get the column name
        for cell in col:
            try: # Necessary to avoid error on empty cells
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width


def xlref(row, column, zero_indexed=True):
    if zero_indexed:
        row += 1
        column += 1
    return get_column_letter(column) + str(row)


def get_value(key, item):
    
    """
    key + value = item
    function return value for given key and item
    """
    if key == item.lstrip():
        return key
    else:
        item = item.lstrip()
        result = re.search('^('+key+')(.*)', item)
        return format(result.group(2)).lstrip()


def get_Switch_info(file_path):

    """
    Loads interface and Vlan specific parts of switch configuration
    into python object.

    The portkeys object (see under docstring) is used to determine how interface lines
    of config are stored in dicts. For example if line "switchport mode access" is
    read then key "3" is used because number of words is equal to three. After lookup
    in the dict the key of "switchmode mode access" is equal to "switchport mode" and
    the value now can be determined using the get_value helper function. To keep it simple
    storing of multiple values per key (for example secundairy ip addresses) is not supported.
    If an interface item is not found in the portkeys object a message is printed to stdout.
    """

    portkeys = { 1: ['switchport' , 'shutdown'] ,
                 2: ['spanning-tree', 'switchport', 'negotiation', 'priority-queue', 'cdp enable'] ,
                 3: ['spanning-tree bpduguard' , 'switchport mode' , 'ip pim' , 'vrf forwarding', 'ip helper-address',
                    'carrier-delay', 'spanning-tree portfast', 'spanning-tree bpdufilter', 'storm-control action'] ,
                 4: ['switchport access vlan' , 'ip address' , 'channel-group', 'storm-control broadcast level', 
                    'switchport voice vlan', 'mls qos trust','auto qos voip', 'switchport port-security',
                     'ip access-group', 'spanning-tree'],
                 5: [] , 6: [] ,
                 7: ['srr-queue bandwidth share', 'srr-queue bandwidth shape'] ,
                 8: [] , 9: [] , 10: [] }
                  

    Portinfo = defaultdict(dict)
    Vlaninfo = defaultdict(dict)
    Switchinfo = defaultdict(dict)
    Intfs = []
    Vlans = []

    with open(file_path, 'r') as lines:
        scanfile = False
        for line in lines:
            line = line.rstrip()
            word = line.split()
            
            match1a = re.search('^interface Vlan(\d+)', line)
            match1b = re.search('^vlan (\d+)\-(\d+)$', line)
            match1c = re.search('^vlan (\d+)$', line)
            match1d = re.search('^interface (.*)' , line)
            match2 = re.search('^ description (.*)', line)
            match2b = re.search('^ name (.*)', line)
            match3 = re.search('^ no (.*)', line)
            match4 = re.search('^hostname (.*)', line)
            match5 = re.search('^ (.*)', line)
            match10 = re.search('^ip forward-protocol nd', line)
            match10a = re.search('^ip classless', line)
            
            if match1a:
                intf = format(match1a.group(0))
                vlan = format(match1a.group(1))
                scanfile = True
                
            elif match1b:
                for vlan in range(int(match1b.group(1)), (int(match1b.group(2))+1)):
                    Vlans.append(str(vlan))

            elif match1c:
                vlan = format(match1c.group(1))
                Vlans.append(vlan)

            elif match1d:
                intf = format(match1d.group(1))
                Intfs.append(intf)
                scanfile = True
                
            elif match2:
                Portinfo[intf]['description'] = format(match2.group(1))

            elif match2b:
                Vlaninfo[vlan]['name'] = format(match2b.group(1))

            elif match3:
                if scanfile:
                    if 'Vlan' in intf:
                        Vlaninfo[vlan][format(match3.group(1))] = format(match3.group(0))
                    else:
                        Portinfo[intf][format(match3.group(1))] = format(match3.group(0))

            elif match4:
                hostname = format(match4.group(1))
            
            elif match5 and scanfile:
                founditem = False
                for portkey in portkeys[len(word)]:
                    if portkey in line:
                        if intf == 'interface Vlan1':
                            founditem = True
                            continue
                        elif 'Vlan' in intf:
                            Vlaninfo[vlan][portkey] = get_value(portkey, line)
                            founditem = True
                        else:
                            Portinfo[intf][portkey] = get_value(portkey, line)
                            founditem = True
                if not founditem:
                    print('The following interface item was not scanned: {}'.format(line))

            elif match10:
              scanfile = False

            elif match10a:
              scanfile = False

        Vlans = sorted(set(Vlans))
        Vlans.sort(key=int)
        Switchinfo['portinfo'] = Portinfo
        Switchinfo['vlaninfo'] = Vlaninfo
        Switchinfo['generalinfo']['hostname'] = hostname
        
        return Switchinfo, Vlans, Intfs



def calc_vlan_use(Switchinfo, Vlans):

    """
    This function returns Vlan usage statistics of the switch. Helpfull if switch is true (stub) access switch.
    """

    used_vlans = []
    for intf in Switchinfo['portinfo']:
        for k,v in Switchinfo['portinfo'][intf].items():
            if Switchinfo['portinfo'][intf].get('channel-group', '') == '': # Do not analyze member intf's of Port-ch's
                if k == 'switchport access vlan':
                    used_vlans.append(Switchinfo['portinfo'][intf]['switchport access vlan'])
    for vlan in Switchinfo['vlaninfo']: # Add Vlan if SVI exists
        if Switchinfo['vlaninfo'][vlan].get('ip address', '') != '':
            used_vlans.append(vlan)

    used_vlans = sorted(set(used_vlans))
    used_vlans.sort(key=int)
    diff  = sorted(set(Vlans).symmetric_difference(set(used_vlans)))
    diff.sort(key=int)

    result = []
    result.append('The following VLANs are present on the switch: ' + ',' .join(Vlans))
    result.append("The following VLANs are present on all access ports and SVI's: "  + ',' .join(used_vlans))
    result.append('The following VLANs are candidate to be removed: ' + ',' .join(diff))
    
    return result

        

def info_to_xls(Switchinfo, Vlans, Intfs, file_path):

    """
    Function print Switchinfo object to excel file. The primary
    keys of Switchinfo object are printed in seperated tabs.
    """

    # Calculate list of keys to be present in Excel sheets
    vlankeys = []
    portkeys = []
    for vlanid in Vlans:
        for vlanid in Switchinfo['vlaninfo']:
            for key in Switchinfo['vlaninfo'][vlanid]:
                vlankeys.append(key)

    for intf in Intfs:
        for intf in Switchinfo['portinfo']:
            for key in Switchinfo['portinfo'][intf]:
                portkeys.append(key)

    vlankeys = sorted(set(vlankeys))
    portkeys = sorted(set(portkeys))
    vlankeys.remove('name')
    portkeys.remove('description')
    vlankeys.insert(0, 'name')
    vlankeys.insert(0, 'vlan')
    portkeys.insert(0, 'description')
    portkeys.insert(0, 'interface')

    wb = Workbook()
    ws = wb.create_sheet("Vlaninfo", 0)
    ws = wb.create_sheet("Portinfo", 0)
    ws = wb.create_sheet("Vlan_report", 0)

    ws = wb['Vlaninfo']

    for count, vlanitem in enumerate(vlankeys):
        ws[xlref(0, count)] = vlanitem

    for count_row, vlan in enumerate(Vlans):
        for count_col, vlanitem in enumerate(vlankeys):
            if count_col == 0:
                ws[xlref(count_row+1, count_col)] = vlan
            else:
                ws[xlref(count_row+1, count_col)] = Switchinfo['vlaninfo'][vlan].get(vlanitem, '')

    xl_adjust_column_width(ws)

    ws = wb['Portinfo']

    for count, portitem in enumerate(portkeys):
        ws[xlref(0, count)] = portitem

    for count_row, intf in enumerate(Intfs):
        for count_col, portitem in enumerate(portkeys):
            if count_col == 0:
                ws[xlref(count_row+1, count_col)] = intf
            else:
                ws[xlref(count_row+1, count_col)] = Switchinfo['portinfo'][intf].get(portitem, '')

    xl_adjust_column_width(ws)

    ws = wb['Vlan_report']

    for count, line in enumerate(calc_vlan_use(Switchinfo, Vlans)):
        ws[xlref(count, 0)] = line
    xl_adjust_column_width(ws)
     
    wb.save(Switchinfo['generalinfo']['hostname'] + '.xlsx')


def add_interface_properties(Switchinfo):

    """
    Interface properties of switch are inserted in Switchinfo object based on
    configuration of all ports. 
    """

    #Add interface properties (access, ip, trunk, unused) to Switchinfo object.
    for intf in Switchinfo['portinfo']:
        if Switchinfo['portinfo'][intf].get('switchport access vlan', '') != '':
            Switchinfo['portinfo'][intf]['mode'] = 'access'
        elif Switchinfo['portinfo'][intf].get('switchport mode', '') == 'trunk':
            Switchinfo['portinfo'][intf]['mode'] = 'trunk'
        elif Switchinfo['portinfo'][intf].get('switchport', '') == 'no switchport':
            Switchinfo['portinfo'][intf]['mode'] = 'ip'
        elif Switchinfo['portinfo'][intf].get('ip address', '') == 'no ip address': # management interface
            Switchinfo['portinfo'][intf]['mode'] = 'unused'
        elif Switchinfo['portinfo'][intf].get('ip address', '') != '': # management interface
            Switchinfo['portinfo'][intf]['mode'] = 'ip'
        else:
            Switchinfo['portinfo'][intf]['mode'] = 'unused'

    for vlan in Switchinfo['vlaninfo']:
        if Switchinfo['vlaninfo'][vlan].get('ip address', '') == 'no ip address':
            Switchinfo['vlaninfo'][vlan]['mode'] = 'ip'
        elif Switchinfo['vlaninfo'][vlan].get('ip address', '') != '':
            Switchinfo['vlaninfo'][vlan]['mode'] = 'ip'

    return Switchinfo
    


def read_config_template(config_template_file):

    """
    config template file is read. The file consists of general, hierarchical and interface configuration
    parts. For each type of interface (IP, access, trunk) a template can be made; also items can be
    exclude for comparison with switch config. Listed items in hierarchical config parts must be
    separate by ! sign. Also after the last item a ! must be present. 
    
    """

    #Read config template and store in object.
    template_object = defaultdict(list)
    with open(config_template_file, 'r') as lines:
        hierarc_scan = False # State var to store hierarchical config parts
        hierarc_temp = [] # store hierarc config item

        for line in lines:
            line = line.rstrip()
            if line.strip():
                
                if line == '# Access interface items':
                    scan_item = 'acc_intf'
                elif line == '# Access interface items ignore':
                    scan_item = 'acc_intf_ign'
                elif line == '# Trunk interface items':
                    scan_item = 'trk_intf'
                elif line == '# Trunk interface items ignore':
                    scan_item = 'trk_intf_ign'
                elif line == '# IP interface items':
                    scan_item = 'ip_intf'
                elif line == '# IP interface items ignore':
                    scan_item = 'ip_intf_ign'
                elif line == '# Global config items':
                    scan_item = 'glob'
                elif line == '# Global items beginning ignore':
                    scan_item = 'glob_begin_ign'
                elif line == '# Global items subset ignore':
                    scan_item = 'glob_subset_ign'
                elif line == '# Global hierarchical config items':
                    hierarc_scan = True
                else:
                    if hierarc_scan:
                        if line == '!':
                            template_object['global_hierarc'].append(hierarc_temp) # store list in list
                            hierarc_temp = []
                        else:
                            hierarc_temp.append(line)

                    else:
                        template_object[scan_item].append(line)
    return template_object


def gen_intf_comparison(Switchinfo, template_object):

    """
    Differences between interface specific switch configuration and template are printed.
    A configuration is presented to shutdown all unused ports. 
    """

    # Open file to report complaincy results
    comparison_file = Switchinfo['generalinfo']['hostname']  + '-comparison-result.txt'

    with open(comparison_file, 'w') as res:

        # Create list with unused ports and shutdown if not already
        print('################ Shutdown unused interfaces:', file=res)
        for intf in Switchinfo['portinfo']:
            for k,v in Switchinfo['portinfo'][intf].items():
                if k == 'mode' and v == 'unused':
                    if Switchinfo['portinfo'][intf].get('shutdown', '') != 'shutdown':
                        print('interface ' + intf, file=res)
                        print(' shutdown', file=res)
                        print('!', file=res)

        # Print access, trunk and IP complaincy reports.
        comparison_intf_info = [('access', 'acc_intf_ign', 'acc_intf'), ('trunk', 'trk_intf_ign', 'trk_intf'),
                           ('ip', 'ip_intf_ign', 'ip_intf')]

        for intf_type, comparison_intf_ign, comparison_intf in comparison_intf_info:
            print('!', file=res)
            print('################ Configure {} ports according template:'.format(intf_type), file=res)
            for intf in Switchinfo['portinfo']:
                found = [] # Relevant configured items under interfaces
                for k,v in Switchinfo['portinfo'][intf].items():
                    if k == 'mode' and v == intf_type:
                        if Switchinfo['portinfo'][intf].get('channel-group', '') == '': # Do not analyze member intf's of Port-ch's
                            print('interface ' + intf, file=res)
                            for k,v in Switchinfo['portinfo'][intf].items():
                                if intf_type == 'access':
                                    if k != 'mode' and k!= 'switchport access vlan':
                                        if k not in template_object[comparison_intf_ign]:
                                            v = v.lstrip()
                                            v_list = v.split()
                                            if k == v:
                                                found.append(k)
                                            elif k == ' '.join(v_list[1:]):
                                                found.append(v)
                                            else:
                                                found.append(k + ' ' + v)
                                else:
                                    if k != 'mode':
                                       if k not in template_object[comparison_intf_ign]:
                                            v = v.lstrip()
                                            v_list = v.split()
                                            if k == v:
                                                found.append(k)
                                            elif k == ' '.join(v_list[1:]):
                                                found.append(v)
                                            else:
                                                found.append(k + ' ' + v)
                                      
                            for item in template_object[comparison_intf]:
                                if item not in found:
                                    print(item, file=res)
                            for item in found:
                                if item not in template_object[comparison_intf] and item not in template_object[comparison_intf_ign]:
                                    print('no ' + item, file=res)
                            print('!', file=res)

        for vlan in Switchinfo['vlaninfo']:
            for k,v in Switchinfo['vlaninfo'][vlan].items():
                if k == 'mode' and v == 'ip':
                    print('interface Vlan' + vlan, file=res)
                    found = []
                    for k,v in Switchinfo['vlaninfo'][vlan].items():
                        if k != 'mode' and k != 'name':
                            if k not in template_object['ip_intf_ign']:
                                v = v.lstrip()
                                value = v.split()
                                if k == v:
                                    found.append(k)
                                elif k == ' '.join(value[1:]):
                                    found.append(v)
                                else:
                                    found.append(k + ' ' + v)
                    
                    for item in template_object['ip_intf']:
                        if item not in found:
                            print(item, file=res)
                    for item in found:
                        if item not in template_object['ip_intf_ign'] and item not in template_object['ip_intf']:
                            print('no ' + item, file=res)
                    print('!', file=res)
                            

    return comparison_file


def gen_hier_config_part_names(file_path):

    """
    This function make list of all first line of all hierarchical config parts. The result is used to filter out
    these parts out of switch configuration in next function because only hierarchical config parts in config template
    are compared to switch configuration.
    """

    with open(file_path, 'r') as lines:

        hier_config_part_names = []
        temp = ''
        hier_var = False
        for line in lines:
            if line.strip():
                line = line.rstrip()

                if line == line.lstrip():
                    match = re.search('^(interface|vlan|banner|ip access-list)(.*)', line) # hard code exceptions
                    if match:
                        hier_config_part_names.append(line)
                    else:
                        temp = line
                else:
                    if not hier_var:
                        hier_config_part_names.append(temp)
                        hier_var = True
                        temp = ''

                if hier_var:
                    if line == '!':
                        hier_var = False

    return hier_config_part_names       

                                


def gen_audit_config(template_object, hier_config_part_names, file_path):

    """
    This function filters out items from switch config. The result is compared
    to config template in last function.
    """

    
    with open(file_path, 'r') as lines:
        skipline = False # If true, config part is ignored
        audit_config = [] # Includes global config items 
        temp_hierarc = [] # Store hierarchical config part
        audit_hierarc_config = [] # List of hierarchical config parts
        hier_var = False # If true hierarchical config is stored

        global_hierarc_template_items = []
        for item in template_object['global_hierarc']:  
            global_hierarc_template_items.append(item[0]) # First line of all lists

        for line in lines:
            if line.strip():
                line = line.rstrip()
                words = line.split()

                if hier_var:
                    if line != line.lstrip():
                        temp_hierarc.append(line)
                    elif line == line.lstrip(): 
                        audit_hierarc_config.append(temp_hierarc)
                        hier_var = False
                    elif line == '!':
                        audit_hierarc_config.append(temp_hierarc)
                        hier_var = False

                for item in global_hierarc_template_items:
                    if line == item:
                        hier_var = True
                        temp_hierarc = []
                        temp_hierarc.append(line)
 
                for item in hier_config_part_names:
                    if item == line:
                        skipline = True
                                  
                if skipline or hier_var:
                    if line == '!':
                        skipline = False
                else:
                    filterline = False
                    for item in template_object['glob_begin_ign']:
                        result = re.search('^('+item+')*',line)
                        if result.group(0):
                            filterline = True
                    for item in template_object['glob_subset_ign']:
                        items = item.split()
                        if set(items).issubset(words):
                            filterline = True                          
                    if not filterline:
                        audit_config.append(line)

        
##        for config in audit_config:
##            print(config)
##
##        print(audit_hierarc_config)
 

    return audit_config, audit_hierarc_config


def gen_general_differences(comparison_file, template_object, audit_config, audit_hierarc_config):
    
    """
    This function presents differences between switch configuration and configuration template.
    The result presents suggestions to remediate the differences.
    """

    with open(comparison_file, 'a') as res:

        non_complaint_items = list(set(audit_config) - set(template_object['glob']))
        print('################ Non compliant General items:', file=res) 
        for item in sorted(non_complaint_items):
            words = item.split()
            if words[0].lstrip() != 'no':
                print('no ' + item, file=res)
            else:
                print(' '.join(words[1:]), file=res)
        print('!', file=res)
        print('################ Missing general template items:', file=res)
        for item in template_object['glob']:
            if item not in audit_config:
                print(item, file=res)

        print('################ Non compliant hierarchical items:', file=res)
        global_hierarc_template_items = [] 
        for item in template_object['global_hierarc']:  
            global_hierarc_template_items.append(item[0]) # First line of all lists

        global_hierarc_config_items = []
        for item in audit_hierarc_config:  
            global_hierarc_config_items.append(item[0]) # First line of all lists

        print('!', file=res)
        diff = set(global_hierarc_template_items) - set(global_hierarc_config_items)
        if diff:
            print('Difference(s) found in hierarchical config sections. Present in template, not in config:', file=res)
            for item in diff:
                for item1 in template_object['global_hierarc']:
                    if item1[0] == item:
                        for item in item1:
                            print(item, file=res)
                        print('!', file=res)

        for index,item in enumerate(template_object['global_hierarc']): # Remove list not found in config
            if item[0] in diff:
              template_object['global_hierarc'].pop(index)

        template_object['global_hierarc'] = sorted(template_object['global_hierarc'], key=lambda x: x[0])
        audit_hierarc_config = sorted(audit_hierarc_config, key=lambda x: x[0])

        #print(template_object['global_hierarc'])

        for hierconf_part, hierconf_configpart in zip(template_object['global_hierarc'], audit_hierarc_config):
            if hierconf_part != hierconf_configpart:
                print('Difference found in {}.'.format(hierconf_part[0]), file=res)
                print('!', file=res)
                print('Template configuration is:', file=res)
                for item in hierconf_part:
                    print(item, file=res)
                print('!', file=res)
                print('Switch configuration is:', file=res)
                for item in hierconf_configpart:
                    print(item, file=res)
            print('!', file=res)
            print('!', file=res)
            print('!', file=res)


def main():

    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename() # switch configuration 

    # Retrieve interface and vlan info from configuration file and store in Switchinfo object.
    Switchinfo, Vlans, Intfs = get_Switch_info(file_path)

    # Print Switchinfo object in excel file.
    info_to_xls(Switchinfo, Vlans, Intfs, file_path)

    # Add interface properties (access, trunk, IP, unused)
    add_interface_properties(Switchinfo)

    # Read config template and store in object.
    config_template_file = 'config_template.txt'
    template_object = read_config_template(config_template_file)

    # Report interface specific differences with user defined template.
    comparison_file = gen_intf_comparison(Switchinfo, template_object)

    # Generate list with first line of all hierarchical config parts.
    hier_config_part_names = gen_hier_config_part_names(file_path)

    # Filter config items from switch config. Result will be compared with template items in next function.
    audit_config, audit_hierarc_config  = gen_audit_config(template_object, hier_config_part_names, file_path)

    # Calculate and present differences between switch config and template.    
    gen_general_differences(comparison_file, template_object, audit_config, audit_hierarc_config)


main()
    











 











    
                
        
            
                    





                                                                                        
