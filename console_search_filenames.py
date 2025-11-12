import csv
import os
import glob

def confirm_cddoc_files(folder: str):
    os.chdir(folder)
    cddoc_file = os.path.join(folder, 'APP_SPEC', 'XFERDATA', 'CDDOC.DAT')
    with open(cddoc_file, 'r') as file:
        reader = csv.reader(file, delimiter=';')
        for row in reader:
            filename = row[21][1:]
            if not os.path.exists(os.path.join(folder, filename)):
                print(f'File not found: {filename}')
    print(f'Done checking cddoc files')


def confirm_manifest_files(folder: str):
    os.chdir(folder)
    manifest_file = os.path.join(folder, '_manifest.csv')
    with open(manifest_file, 'r') as file:
        reader = csv.reader(file, skipinitialspace=True)
        for row in reader:
            filename = row[2]
            if not os.path.exists(filename):
                print(f'File not found: {filename}')
    print(f'Done checking manifest files')

def rename_x_files(folder: str):
    search_term = 'X'
    # look for files with X in the name
    glob_pattern = os.path.join(folder, '**', '*X*')
    files = glob.glob(glob_pattern, recursive=True)
    for f in files:
        if os.path.isdir(f):
            continue
        parts = os.path.basename(f).split('.')
        stub = parts[0]
        extension = parts[1]
        new_name = stub.split(' ')[0]
        response = input(f'Rename {stub} to {new_name} (y/n): ')
        if response.lower() == 'y':
            new_path = os.path.join(os.path.dirname(f), new_name + '.' + extension)
            os.rename(f, new_path)
            print(f'Renamed {f} to {new_path}')
        else:
            print(f'Skipping {f}')
    print(f'Done renaming files')

if __name__ == "__main__":
    folder = input("Enter the folder to search: ")  
    # rename_x_files(folder)
    confirm_manifest_files(folder)
    # confirm_cddoc_files(folder)