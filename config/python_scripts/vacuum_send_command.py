 #{'entity_id': 'vacuum.rockrobo', 'command': 'app_zoned_clean', 'params': [[29911, 13811, 33116, 17067, 1]]}
 
backGuest = '29911, 13811, 33116, 17067'
frontGuest = '33945, 13551, 38350, 17410'
livingAndKitch = '22690, 22778, 32457, 26013], [22725, 18724, 34759, 22826], [30852, 17148, 34777, 18825], [32605, 16157, 33980, 17196'
nickCloset = '26920, 16975, 29805, 18513'
nickRoom = '22689, 17452, 26864, 18697], [22721, 14028, 29985, 17449'

entity_id = data.get('entity_id')
command = data.get('command')
params = str(data.get('params'))
parsedParams = []
repeats = 1
zone_id = ''
finalParams = []

if ' 1]' in params:
#    print("repeats is 1")
    repeats = 1

if ' 2]' in params:
#    print("repeats is 2")
    repeats = 2

if ' 3]' in params:
#    print("repeats is 3")
    repeats = 3

#for x in params.replace(', 1]',']').replace(', 2]',']').replace(', 3]',']').

for z in params.replace(', 1]',']').replace(', 2]',']').replace(', 3]',']').replace(' ', '').replace('],[', '|').replace('[', '').replace(']', '').split('|'):
    rect = []
    for c in z.split(','):
        c = float(c)
        rect.append(int(c))
    parsedParams.append(rect)

parsedParams = str(parsedParams).replace('[[','[').replace(']]',']')
#print(parsedParams)
for z in parsedParams.replace(backGuest, 'Back Guest Room').replace(frontGuest, 'Front Guest Room').replace(livingAndKitch, 'Living Room and Kitchen').replace(nickCloset, 'Nicks Closet').replace(nickRoom, 'Nicks Room').replace('],[', '|').replace('[', '').replace(']', '').split('|'):
    rect = []
    for c in z.split(','):
#        rect.append(c)
#        print('c')
#        print(c)
#        print(c[0])
        if c[0] == ' ':
            c = c[1:]
        rect.append(c)
#        print('rect')
#        print(rect)
    finalParams = rect

#print('finalParams')
#print(finalParams)

if command in  ["app_goto_target", "app_segment_clean"]:
    parsedParams = parsedParams[0]

if command == "app_zoned_clean":
    command = "zoned_cleanup"

#if parsedParams == [[29911, 13811, 33116, 17067]]:
#    zone_id = 'Back Guest Room'

#finalParams.append("zone_id: "+zone_id)
#finalParams.append("repeats: "+str(repeats))

#superFinalParams = []

service_data = {"entity_id": entity_id, "command": command, "params": {"zone_ids": finalParams, "repeats": str(repeats)}}

#service_data = {"entity_id": entity_id, "rgb_color": rgb_color, "brightness": 255}command
#hass.services.call("light", "turn_on", service_data, False)

logger.info(service_data)
hass.services.call("vacuum", "send_command",
                   service_data)