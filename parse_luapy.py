lua_path = 'data\HirasawaBot\isaac\eid\zh_cn\collectibles.luapy'
with open(lua_path, 'r', encoding='utf-8') as f:
    lua_code = f.read()


ans = {}

for line in lua_code.split('\n'):
    line = line.split('--')[0].strip()
    if line.endswith(','): line = line[:-1]

    if line.startswith('{') and line.endswith('}'):
        line = f'[{line[1:-1]}]'
        try:
            item = eval(line)
            ans[int(item[0])] = item[1]
        except:
            continue
    elif line.startswith('['):
        exec(f'ans{line}')
    else:
        continue

print(len(ans))
        
    


