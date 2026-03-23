import os
import subprocess
import argparse
import sys
import csv
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Global lock for thread-safe CSV writing
csv_lock = threading.Lock()

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

def process_single_file(file_info, script_path, csv_writer, csv_file, pbar=None):
    """
    Worker function to process a single video file.
    """
    full_path, display_path, csv_path = file_info
    
    metadata, error = get_video_metadata(script_path, full_path)
    
    if metadata:
        # RESULT_METADATA|filename|duration|datetime|lat|long|max_faces|face_ids_count|face_details|scene_details
        row = [display_path] + metadata[2:]
        
        with csv_lock:
            if csv_writer:
                csv_writer.writerow(row)
                csv_file.flush()
            msg = f"Processed: {display_path} (Duration={metadata[2]}s, Max Faces={metadata[6]}, Distinct Faces={metadata[7]})"
            if pbar:
                pbar.write(msg)
            else:
                print(msg)
    else:
        msg = f"Failed: {display_path} - {error}"
        if pbar:
            pbar.write(msg)
        else:
            print(msg)
            
    if pbar:
        pbar.update(1)

def process_mounted_dir(mount_path, script_path, csv_path=None, dry_run=False, num_workers=40):
    """
    Recursively walks the mounted directory and filters for the video structure.
    Processes files in parallel using ThreadPoolExecutor with a tqdm progress bar.
    """
    if not os.path.exists(mount_path):
        print(f"Error: Mount path '{mount_path}' does not exist.")
        return

    print(f"Scanning mounted directory: {mount_path}...")
    
    eligible_files = []
    
    for root, dirs, files in os.walk(mount_path):
        for file in files:
            if file.lower().endswith(".mp4"):
                rel_path = os.path.relpath(root, mount_path)
                parts = rel_path.split(os.sep)
                
                # Filter for: <user>/<subfolder>/source/default/*.mp4
                if len(parts) >= 2 and parts[-2] == "source" and parts[-1] == "default":
                    full_path = os.path.join(root, file)
                    display_path = os.path.join(rel_path, file)
                    eligible_files.append((full_path, display_path, csv_path))

    if not eligible_files:
        print("No matching videos found in the specified path structure.")
        return

    print(f"Found {len(eligible_files)} videos. Starting parallel processing (workers={num_workers})...\n")
    
    if dry_run:
        for _, display_path, _ in eligible_files:
            print(f"[Dry Run] Found: {display_path}")
        return

    csv_file = None
    csv_writer = None
    headers = ["File Path", "Duration (s)", "DateTime (UTC)", "Latitude", "Longitude", "Max Faces", "Distinct Faces", "Face Details", "Scene Classifier"]
    
    if csv_path:
        file_exists = os.path.isfile(csv_path)
        csv_file = open(csv_path, mode='a', newline='')
        csv_writer = csv.writer(csv_file)
        if not file_exists:
            csv_writer.writerow(headers)
            csv_file.flush()

    try:
        with tqdm(total=len(eligible_files), desc="Processing Videos", unit="vid") as pbar:
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = [executor.submit(process_single_file, f, script_path, csv_writer, csv_file, pbar) for f in eligible_files]
                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        pbar.write(f"Worker generated an exception: {e}")
    finally:
        if csv_file:
            csv_file.close()

    print(f"\nFinished processing {len(eligible_files)} videos.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch process GCMF video durations and metadata via gcsfuse mount with multithreading.")
    parser.add_argument("--mount", required=True, help="Path to the gcsfuse mount directory")
    parser.add_argument("--script", default="./get_duration.sh", help="Path to get_duration.sh")
    parser.add_argument("--csv", default="video_metadata_batch.csv", help="Output CSV file name")
    parser.add_argument("--workers", type=int, default=40, help="Number of parallel workers (default: 40)")
    parser.add_argument("--dry-run", action="store_true", help="List files without processing")
    
    args = parser.parse_args()
    
    if os.path.exists(args.script):
        os.chmod(args.script, 0o755)
    
    process_mounted_dir(args.mount, args.script, args.csv, args.dry_run, args.workers)
