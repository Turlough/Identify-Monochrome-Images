
def validate_ref(item:str) -> bool:
    return len(item) == 7 

def validate_filename(item:str) -> bool:
    stub = item.split('.')[0]
    return len(stub) == 7

text_file = input("Enter the text file to validate: ")

with open(text_file, 'r') as file:
    seen_refs = set()
    for line in file:
        items = line.strip().split(',')

        ref = items[1]
        filename = items[2]

        # if ref in seen_refs:
        #     print(f"Duplicate reference: {ref}, {filename}")
        # else:
        #     seen_refs.add(ref)

        if not validate_ref(ref):
            print(f"Invalid item: {ref}")
        if not validate_filename(filename):
            print(f"Check filename: {filename}")