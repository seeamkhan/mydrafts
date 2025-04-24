
import re

def extract_dialogue(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    dialogue_lines = []
    for line in lines:
        # Skip lines that contain speaker tags or timestamps
        if re.match(r'^\d+\s+".*"\s+\(\d+\)', line):
            continue
        elif re.match(r'^\d{2}:\d{2}:\d{2}\.\d+\s*[-|>]+\s*\d{2}:\d{2}:\d{2}\.?\d*', line):
            continue
        elif line.strip() == "":
            continue
        else:
            dialogue_lines.append(line.strip())

    # Combine dialogue into a single string with line breaks
    return '\n'.join(dialogue_lines)

# Example usage
if __name__ == "__main__":
    file_path = 'transcript.txt'  # Replace with your actual file name
    cleaned_text = extract_dialogue(file_path)
    print(cleaned_text)
