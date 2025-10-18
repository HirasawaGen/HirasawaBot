from pathlib import Path
import re


from ncatbot.core import (
    PrivateMessage,
    GroupMessage,
    BaseMessageEvent,
    MessageSegment,
    MessageArray,
    Image,
    Text,
    At,
)


def get_icon(name: str, isaac_root: Path) -> Path | None:
    icon = isaac_root / 'icon' / f'{name}.png'
    if name.startswith('Collectible') and len(name) > len('Collectible'):
        collectibles_root = isaac_root / 'items' / 'collectibles'
        for collectible in collectibles_root.iterdir():
            if collectible.suffix != '.png': continue
            if int(collectible.stem.split('_')[1]) == int(name[len('Collectible'):]):
                icon = collectible
    if name.startswith('Trinket') and len(name) > len('Trinket'):
        trinkets_root = isaac_root / 'items' / 'trinkets'
        for trinket in trinkets_root.iterdir():
            if trinket.suffix != '.png': continue
            if int(trinket.stem.split('_')[1]) == int(name[len('Trinket'):]):
                icon = trinket
    if icon.exists():
        return icon
    return None


def load_eid(item_type: str, isaac_root: Path, lang: str = 'zh_cn') -> dict[int, dict]:
    '''
    luapy并不是一种语言，只是一种用类json格式储存的lua数据的字符文件
    以方便我用python解析
    '''
    luapy_path = isaac_root / 'eid' / lang / f'{item_type}.luapy'
    ans: dict[int, dict] = {}
    with open(luapy_path, 'r', encoding='utf-8') as f:
        content = f.read()
    for line in content.split('\n'):
        parts = line.split('--')
        line = parts[0] if len(parts) == 1 else '--'.join(parts[:-1])
        line = line.strip()
        if line.endswith(','): line = line[:-1]

        if line.startswith('{') and line.endswith('}'):
            line = f'[{line[1:-1]}]'
            try:
                item = eval(line)
                key = int(item[0])
                ans[key] = {}
                ans[key]['id'] = item[0]  # key is int, 'id' is str
                ans[key]['name'] = item[1]
                ans[key]['desc'] = item[2]
            except:
                continue
        elif line.startswith('['):
            line = ('='.join(line.split('=')[1:])).strip()
            line = f'[{line[1:-1]}]'
            try:
                item = eval(line)
                key = int(item[0])
                ans[key] = {}
                ans[key]['id'] = item[0]  # key is int, 'id' is str
                ans[key]['name'] = item[1]
                ans[key]['desc'] = item[2]
            except:
                continue  
        else:
            continue
    image_root = isaac_root / 'items' / item_type
    for image in image_root.iterdir():
        if image.suffix != '.png': continue
        stems = image.stem.split('_')
        item_id = int(stems[1])
        if item_id not in ans: continue
        ans[item_id]['raw_name'] = stems[2]
    return ans


def eid_description(item_type: str, isaac_root: Path, info: dict[str, str], no_desc: bool = False) -> list[str | Path]:    
    item_type = item_type.lower()
    name = info['name']
    desc = info['desc']
    item_id = info['id']
    type_in_path = item_type if item_type == 'collectibles' else item_type[:-1]
    image_file = isaac_root / 'items' / item_type / f'{type_in_path}_{info["id"]:0>3}_{info["raw_name"]}.png'
    if no_desc:
        return [image_file, f'道具名称：{name}\n道具id：{item_id}']
    desc = desc.replace('#', '\n')
    desc = desc.replace('↓', '{{ArrowDown}}')
    desc = desc.replace('↑', '{{ArrowUp}}')
    arr: list[str | Path] = [image_file]
    for seg in re.split(
        r'(\{\{.*?\}\})', 
        f'道具名称：{name}\n道具id：{item_id}\n\n{desc}'
    ):
        if not seg.startswith('{{'):
            arr.append(seg)
            continue
        icon = get_icon(seg[2:-2], isaac_root)
        if icon is None:
            arr.append(seg)
            continue
        if isinstance(arr[-1], str) and arr[-1].strip() == '':
            arr[-1] = icon
        else:
            arr.append(icon)
    return arr