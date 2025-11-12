
def validate(item:str) -> bool:
    return len(item) == 13 

text_file = input("Enter the text file to validate: ")
with open(text_file, 'r') as file:
    for line in file:
        items = line.strip().split(',')
        if not validate(items[1]):
            print(f"Invalid item: {items[1]}")