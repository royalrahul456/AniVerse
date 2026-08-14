import json
import os

log_path = r"C:\Users\Rahul Pachute\.gemini\antigravity\brain\a5bcdff1-7b96-41a2-b2be-0c3efb36fb8f\.system_generated\logs\transcript_full.jsonl"
def search():
    if not os.path.exists(log_path):
        print("Log path does not exist.")
        return
        
    with open(log_path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            try:
                data = json.loads(line)
                # Check for USER_INPUT steps or content matching '&' or 'ampersand' or 'and'
                content = str(data.get("content", ""))
                type_ = data.get("type", "")
                source = data.get("source", "")
                
                if source == "USER_EXPLICIT" or "USER" in type_:
                    if "&" in content or "ampersand" in content.lower() or "and" in content.lower():
                        print(f"Step {idx} | Source: {source} | Content: {content}")
            except Exception as e:
                pass

if __name__ == "__main__":
    search()
