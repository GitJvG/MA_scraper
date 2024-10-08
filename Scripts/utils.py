import pandas as pd
import os
import json
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

load_dotenv()
CONFIG = os.getenv('CONFIG')
metadata_path = os.getenv('METADATA')

file_paths = {
    'MA_Bands.csv': ['Band ID'],
    'MA_Similar.csv': ['Band ID', 'Similar Artist ID'],
    'MA_Discog.csv': ['Album Name', 'Type', 'Year', 'Band ID'],
    'MA_Lyrics.csv': ['Band ID'],
    'metadata.csv': ['Filename'],
    'MA_Changes.csv': ['Band ID']
}

def load_config(attribute):
    """Attribute as Cookies or Headers"""
    with open('config.json', 'r') as file:
        config = json.load(file)
        
    return config.get(attribute)

def save_progress(new_data, output_file):
    df_new = pd.DataFrame(new_data)
    unique_columns = file_paths[os.path.basename(output_file)]
    try:
        df_existing = pd.read_csv(output_file, keep_default_na=False)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        # Drop duplicates, keeping the last entry based on the unique columns
        df_updated = df_combined.drop_duplicates(subset=unique_columns, keep='last')
        df_updated.to_csv(output_file, mode='w', header=True, index=False)
         
    except FileNotFoundError:
        df_new.to_csv(output_file, mode='w', header=True, index=False)

    print(f"Progress saved to {output_file}")
    update_metadata(os.path.basename(output_file))

def process_band_ids(band_ids_to_process, batch_size, output_file, function, **kwargs):
    print(f"Total bands to process: {len(band_ids_to_process)}")
    all_band_data = []  # This will now hold DataFrames
    processed_count = 0
    lock = Lock()

    def update_processed_count():
        nonlocal processed_count
        with lock:
            processed_count += 1
            print(f"Processed {processed_count} band IDs.")
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_band_id = {executor.submit(function, band_id, **kwargs): band_id for band_id in band_ids_to_process}

        for future in as_completed(future_to_band_id):
            band_id = future_to_band_id[future]
            try:
                band_data = future.result()
                update_processed_count()
                if not band_data.empty:  # Check if the DataFrame is not empty
                    all_band_data.append(band_data)  # Append DataFrame
                    if processed_count % batch_size == 0:
                        save_progress(pd.concat(all_band_data, ignore_index=True), output_file)  # Concatenate and save
                        all_band_data.clear()  # Clear data after saving
            except Exception as e:
                print(f"Error processing band ID {band_id}: {e}")
    if all_band_data:
        save_progress(pd.concat(all_band_data, ignore_index=True), output_file)  # Final save

def update_metadata(data_filename):
    new_entry = pd.DataFrame([{
        'Filename': data_filename,
        'Date': pd.Timestamp.now().strftime('%Y-%m-%d')
    }])
    
    try:
        metadata_df = pd.read_csv(metadata_path)
        
        # Drop any rows where 'Filename' matches data_filename to avoid duplicates
        metadata_df = metadata_df[metadata_df['Filename'] != data_filename]
        
        # Append the new entry (this ensures the new entry replaces the old one)
        metadata_df = pd.concat([metadata_df, new_entry], ignore_index=True)
        
    except FileNotFoundError:
        # If the metadata file doesn't exist, create a new DataFrame
        metadata_df = new_entry

    metadata_df.to_csv(metadata_path, index=False)

    print('Metadata updated!')
    return metadata_df

def remove_duplicates(file_path):
    """Failsafe measure. Removes duplicates from the CSV file based on unique columns defined in the file_paths dictionary."""
    filename = os.path.basename(file_path)
    
    if filename not in file_paths:
        print(f"No unique columns defined for {filename}. Skipping.")
        return

    df = pd.read_csv(file_path)
    unique_columns = file_paths[filename]
    df_updated = df.drop_duplicates(subset=unique_columns, keep='last')
    df_updated.to_csv(file_path, mode='w', header=True, index=False)
    
    print(f"Duplicates removed and progress saved for {filename}.")