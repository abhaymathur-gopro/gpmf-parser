import os
import subprocess
import argparse
import sys
import csv

def get_video_metadata(script_path, local_path):
    """
    Executes the get_duration.sh script on a local file and returns the metadata line.
    """
    try:
        script = os.path.abspath(script_path)
        if not os.path.exists(script):
            return None, f"Error: Script not found at {script}"
            
        # Run the command with -m flag for machine-readable output
        result = subprocess.run([script, local_path, "-m"], capture_output=True, text=True)
        if result.returncode == 0:
            # Look for the RESULT_METADATA line
            for line in result.stdout.split('\n'):
                if line.startswith("RESULT_METADATA|"):
                    return line.strip().split('|'), None
            return None, "Error: No metadata line found in output."
        else:
            return None, f"Error (Exit {result.returncode}): {result.stderr.strip()}"
    except Exception as e:
        return None, f"Exception: {str(e)}"

def process_mounted_dir(mount_path, script_path, csv_path=None, dry_run=False):
    """
    Recursively walks the mounted directory and filters for the video structure.
    Expects: <user>/<subfolder>/source/default/*.mp4
    """
    if not os.path.exists(mount_path):
        print(f"Error: Mount path '{mount_path}' does not exist.")
        return

    print(f"Scanning mounted directory: {mount_path}...")
    
    csv_file = None
    csv_writer = None
    headers = ["File Path", "Duration (s)", "DateTime (UTC)", "Latitude", "Longitude", "Face Count", "Face Details", "Scene Classifier"]
    
    if csv_path:
        # Check if file exists to write headers
        file_exists = os.path.isfile(csv_path)
        csv_file = open(csv_path, mode='a', newline='')
        csv_writer = csv.writer(csv_file)
        if not file_exists:
            csv_writer.writerow(headers)
            csv_file.flush()

    count = 0
    found_any = False
    
    try:
        for root, dirs, files in os.walk(mount_path):
            for file in files:
                if file.lower().endswith(".mp4"):
                    rel_path = os.path.relpath(root, mount_path)
                    parts = rel_path.split(os.sep)
                    
                    if len(parts) >= 2 and parts[-2] == "source" and parts[-1] == "default":
                        found_any = True
                        full_path = os.path.join(root, file)
                        display_path = os.path.join(rel_path, file)
                        
                        print(f"\n--- Processing: {display_path} ---")
                        
                        if dry_run:
                            print("[Dry Run] Skipping processing.")
                            continue
                            
                        metadata, error = get_video_metadata(script_path, full_path)
                        
                        if metadata:
                            # RESULT_METADATA|filename|duration|datetime|lat|long|face_count|face_details|scene_details
                            # We replace 'filename' with the 'display_path'
                            row = [display_path] + metadata[2:]
                            print(f"Successfully extracted: Duration={metadata[2]}s, Lat={metadata[4]}, Lon={metadata[5]}, Faces={metadata[6]}")
                            
                            if csv_writer:
                                csv_writer.writerow(row)
                                csv_file.flush() # Ensure it's saved incrementally
                                print(f"Row added to {csv_path}")
                        else:
                            print(f"Failed: {error}")
                        
                        count += 1
    finally:
        if csv_file:
            csv_file.close()

    if not found_any:
        print("No matching videos found in the specified path structure.")
    else:
        print(f"\nFinished processing {count} videos.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch process GCMF video durations and metadata via gcsfuse mount.")
    parser.add_argument("--mount", required=True, help="Path to the gcsfuse mount directory")
    parser.add_argument("--script", default="./get_duration.sh", help="Path to get_duration.sh")
    parser.add_argument("--csv", default="video_metadata_batch.csv", help="Output CSV file name")
    parser.add_argument("--dry-run", action="store_true", help="List files without processing")
    
    args = parser.parse_args()
    
    if os.path.exists(args.script):
        os.chmod(args.script, 0o755)
    
    process_mounted_dir(args.mount, args.script, args.csv, args.dry_run)
