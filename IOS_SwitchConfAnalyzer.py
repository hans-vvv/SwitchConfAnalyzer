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


def get_value(key, item): # key + value = item. Function returns value
    if key == item.lstrip():
        return key
    else:
        item = item.lstrip()
        result = re.search('^('+key+')(.*)', item)
        return format(result.group(2)).lstrip()


def get_Switch_info(Switchinfo, Vlans, Intfs, file_path):

    # key is number of words of configuration item. Words in list are key of item. Value to be calculated with get_value function.
    portkeys = { 1: ['switchport' , 'shutdown'] ,
                 2: ['spanning-tree', 'switchport', 'negotiation', 'priority-queue', 'cdp enable'] ,
                 3: ['spanning-tree bpduguard' , 'switchport mode' , 'ip pim' , 'vrf forwarding', 'ip helper-address',
                    'carrier-delay', 'spanning-tree portfast', 'spanning-tree bpdufilter', 'storm-control action'] ,
                 4: ['switchport access vlan' , 'ip address' , 'channel-group', 'storm-control broadcast level', 
                    'switchport voice vlan', 'mls qos trust','auto qos voip', 'switchport port-security'],
                 5: [] , 6: [] ,
                 7: ['srr-queue bandwidth share', 'srr-queue bandwidth shape'] ,
                 8: [] , 9: [] , 10: [] }
                  

    Portinfo = defaultdict(dict)
    Vlaninfo = defaultdict(dict)
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
                for i in range(1, 11):
                    if len(word) == i:
                        founditem = False
                        for portkey in portkeys[i]:
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
        return Switchinfo, Vlans, Intfs, file_path


def calc_vlan_use(Switchinfo, Vlans):

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
    result.append('The following VLANs are present on all access ports: ' + ',' .join(used_vlans))
    result.append('The following VLANs are candidate to be removed: ' + ',' .join(diff))
    
    return result

        

def info_to_xls(Switchinfo, Vlans, Intfs, file_path):

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


def complaincy_report(Switchinfo, compl_template_file, file_path):

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

    #Read complaincy template and store in object.
    compl_template = defaultdict(list)
    with open(compl_template_file, 'r') as lines:
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
                elif line == '# Console':
                    scan_item = 'con'
                elif line == '# VTY':
                    scan_item = 'vty'
                elif line == '# Global complaincy items':
                    scan_item = 'glob'
                elif line == '# Global nested items ignore':
                    scan_item = 'glob_nest_ign'
                elif line == '# Global items beginning ignore':
                    scan_item = 'glob_begin_ign'
                elif line == '# Global items subset ignore':
                    scan_item = 'glob_subset_ign'
                else:
                   compl_template[scan_item].append(line) 
                            
    # Open file to report complaincy results
    complaince_file = Switchinfo['generalinfo']['hostname']  + '-complaince-result.txt'

    with open(complaince_file, 'w') as res:

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
        complaincy_intf_info = [('access', 'acc_intf_ign', 'acc_intf'), ('trunk', 'trk_intf_ign', 'trk_intf'),
                           ('IP', 'ip_intf_ign', 'ip_intf')]

        for intf_type, compl_intf_ign, compl_intf in complaincy_intf_info:
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
                                        if k not in compl_template[compl_intf_ign]:
                                            found.append(k + ' ' + v)
                                else:
                                    if k != 'mode':
                                       if k not in compl_template[compl_intf_ign]:
                                            found.append(k + ' ' + v) 
                            for item in compl_template[compl_intf]:
                                if item not in found:
                                    print(item, file=res)
                            for item in found:
                                if item not in compl_template[compl_intf]:
                                    print('no ' + item, file=res)
                            print('!', file=res) 
        

    # Read config and create list with selected (via template) config items. This list will be compared to
    # items present in indented part of template. Differences are reported. Also VTY and console config
    # items are compared and reported.
    with open(file_path, 'r') as lines:
        skipline = False # If true, (nested) config part is ignored
        scantransportlines = False # if true console and VTY items are read from config
        config = [] # Includes config items to be compared with indented items in template
        transportlines = {}
        for line in lines:
            if line.strip():
                line = line.rstrip()
                words = line.split()
                
                for item in compl_template['glob_nest_ign']:
                    if item in line:
                        if line.strip():
                            items = item.split()
                            if items[0] == words[0]:
                                skipline = True 

                if line == '!':
                    scantransportlines = False

                if words[0] == 'line': # initialize dict to store items in lists from VTY and console.
                    scantransportlines = True
                    if words[1] == 'con':
                        transportline = 'con'
                        transportlines[transportline] = []        
                    elif words[1] == 'vty' and words[3] == '4':
                        transportline = 'vty04'
                        transportlines[transportline] = []
                    elif words[1] == 'vty' and words[3] == '15':
                        transportline = 'vty515'
                        transportlines[transportline] = []

                if scantransportlines and words[0] != 'line':
                        transportlines[transportline].append(line.lstrip())
                    
                if skipline:
                    if line == '!':
                        skipline = False
                else: 
                    filterline = False
                    for item in compl_template['glob_begin_ign']:
                        result = re.search('^('+item+')*',line)
                        if result.group(0):
                            filterline = True
                    for item in compl_template['glob_subset_ign']:
                        items = item.split()
                        if set(items).issubset(words):
                            filterline = True                          
                    if not filterline:
                        config.append(line)

##        for configline in config: # Use to debug which config parts are filtered through configuration.
##            print(configline)

    with open(complaince_file, 'a') as res:

        # Calculate differences for Console, VTY and general configuration items and print.
        complaincy_general_info = [('console', 'con', 'con'), ('VTY 0 4', 'vty04', 'vty'),
                                   ('VTY 5 15', 'vty515', 'vty'), ('General', 'config', 'glob')]
        
        for compl_type, compl_line_type, compl_template_type in complaincy_general_info:
            
            print('!', file=res)
            if compl_type != 'General':
                non_complaint_items = list(set(transportlines[compl_line_type]) - set(compl_template[compl_template_type]))
            else:
                non_complaint_items = list(set(config) - set(compl_template['glob']))
            print('################ Non compliant {} items:'.format(compl_type), file=res) 
            for item in sorted(non_complaint_items):
                words = item.split()
                if words[0].lstrip() != 'no':
                    print('no ' + item, file=res)
                else:
                    print(' '.join(words[1:]), file=res)
            print('!', file=res)
            print('################ Missing {} items:'.format(compl_type), file=res)
            if compl_type != 'General':
                for item in compl_template[compl_template_type]:
                    if item not in transportlines[compl_line_type]:
                        print(item, file=res)
            else:
                for item in compl_template['glob']:
                    if item not in config:
                        print(item, file=res)

def main():

    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename()
    Switchinfo = defaultdict(dict)
    Vlans = []
    Intfs = []
    Switchinfo, Vlans, Intfs, file_path = get_Switch_info(Switchinfo, Vlans, Intfs, file_path)
      
    info_to_xls(Switchinfo, Vlans, Intfs, file_path)
    compl_template_file = 'complaincy template.txt'
    complaincy_report(Switchinfo, compl_template_file, file_path)

main()
    











 











    
                
        
            
                    





                                                                                        
