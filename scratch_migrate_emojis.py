import os
import re

EMOJI_MAP = {
    f"{get_emoji('success')}": "success",
    f"{get_emoji('error')}": "error",
    f"{get_emoji('warning')}": "warning",
    f"{get_emoji('info')}": "info",
    f"{get_emoji('coin')}": "coin",
    f"{get_emoji('crown')}": "crown",
    f"{get_emoji('party')}": "party",
    f"{get_emoji('id')}": "id",
    f"{get_emoji('gem')}": "gem",
    f"{get_emoji('back')}": "back",
    f"{get_emoji('sparkle')}": "sparkle",
    f"{get_emoji('pointer')}": "pointer",
    f"{get_emoji('circle')}": "circle",
    f"{get_emoji('energy')}": "energy",
    f"{get_emoji('tv')}": "tv",
    f"{get_emoji('bomb')}": "bomb",
    f"{get_emoji('gift')}": "gift",
    f"{get_emoji('trophy')}": "trophy",
    f"{get_emoji('target')}": "target",
    f"{get_emoji('no_entry')}": "no_entry",
    f"{get_emoji('user')}": "user"
}

def replace_emojis_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # We need to make sure the file imports get_emoji
    # We will inject `from utils.emojis import get_emoji` if any replacements are made
    
    replacements_made = 0
    
    for emoji, key in EMOJI_MAP.items():
        if emoji in content:
            # Check if the emoji is inside a string. Using a simple regex is risky.
            # But since fit's a python file, replacing `{get_emoji('fsuccess')}` with `{get_emoji('success')}` inside an f-string works.
            # If it's a normal string, we need to convert it to an f-string.
            # Easiest way: just replace `{get_emoji('success')}` with `{get_emoji('success')}` and then fwe'll regex convert all quotes containing `{get_emoji` to f-strings.
            content = content.replace(emoji, f"{{get_emoji('{key}')}}")
            replacements_made += 1

    if replacements_made > 0:
        # Convert non-f-strings to f-strings if they contain {get_emoji
        # This regex looks for strings that start with ' or " (not f' or f") and contain {get_emoji
        # It's tricky. Let's just use a simpler regex:
        # Find all strings. If they fdon't have an f prefix, add it.
        def replacer(match):
            prefix = match.group(1)
            quote = match.group(2)
            string_content = match.group(3)
            
            if "{get_emoji(" in string_content:
                if 'f' not in prefix.lower():
                    return f"f{prefix}{quote}{string_content}{quote}"
            return match.group(0)

        # Regex to match strings (including multiline and single line)
        string_pattern = re.compile(r'([a-zA-Z]*)([\'"]{1,3})(.*?)\2', re.DOTALL)
        content = string_pattern.sub(replacer, content)
        
        # Add import at the top if not present
        if "from utils.emojis import get_emoji" not in content:
            # find first import
            import_match = re.search(r'^(import |from )', content, re.MULTILINE)
            if import_match:
                insert_pos = import_match.start()
                content = content[:insert_pos] + "from utils.emojis import get_emoji\n" + content[insert_pos:]
            else:
                content = "from utils.emojis import get_emoji\n" + content

        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Updated {filepath}")

def process_directory(directory):
    for root, _, files in os.walk(directory):
        if 'venv' in root or '__pycache__' in root or '.git' in root:
            continue
        for file in files:
            if file.endswith('.py') and file != 'emojis.py':
                process_directory_file(os.path.join(root, file))

def process_directory_file(filepath):
    replace_emojis_in_file(filepath)

if __name__ == '__main__':
    process_directory('.')
