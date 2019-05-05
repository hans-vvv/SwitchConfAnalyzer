# SwitchConfAnalyzer

In my journey to gain experience in Network automation I have made a Python script to analyze IOS based multilayer switch configurations. The script has the following capabilities:

1. It reads the configuration and store interface and vlan items, which are written to an excel file. Using excel features like autofilter you can analyze the specific interface and vlan configuration parts of the switch. 

2. In a template file you can specify several items to which the configuration must comply. The following categories can be specified:
- Switchport access interfaces
- Switchport trunk interfaces
- IP interfaces
- General configuration items
- Hierarchical configuration items

There are some (hopefully) self explanatory filters in the template file available in order to determine which items are to be skipped for comparison with the intended configuration. 

When you run the script you must select the configuration file via a file dialog. Within the same directory the template file must be present. If all goes well (...) then two files are returned, the excel file and a file with differences to the intended configuration.

My biggest challenge to accomplish this result was to find a convenient way to store and structure the data. I found the defaultdict very helpfull because you can save items in a nested structure without having to initialize a dictionary. Futhermore I choose a structure with "look and feel" to the way you store data in an excel file. So for example if you want to retreive information about the description of interface Port-channel10 you can access the dictionary Switchinfo as follows:

Switchinfo['portinfo']['interface Port-channel 10']['description']

The first key represent the tab which is present in the excel file. Using a simular structure it is possible to store a big network into a single excel file. 

The following caveats apply to the script:
- No support for subinterfaces
- Script only analyze port-channel interfaces and not it's member interfaces




