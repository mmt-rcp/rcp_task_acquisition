import pandas as pd
import numpy as np



def identify_dropped_frames(timestamp_file, frame_rate):
    """
    Identify dropped frames in a video based on inter-frame intervals.
 
    Parameters:
        timestamp_file (str): Path to the CSV file containing timestamps in nanoseconds.
        frame_rate (float): Expected frame rate in frames per second.
 
    Returns:
        frame_count (int): Number of dropped frames. 
    """
    
    #getting frame count from timestamps (less accurate but catches sync issues)
    timestamps_ns = pd.read_csv(timestamp_file)['timestamp'].values[1:]  # Extract timestamp column
    expected_interval = 1e9 / frame_rate
    current_frame = len(timestamps_ns)
    timestamps_ns = np.asarray(timestamps_ns)
    dropped_frame_count = np.sum((np.round(timestamps_ns / expected_interval)) - 1)
    total_frames = current_frame+dropped_frame_count
    
    #getting frame count by frame count
    frames_list = pd.read_csv(timestamp_file)['frame_id'].values[1:]  
    frame_arr = np.asarray(frames_list)
    frame_len = len(frame_arr)
    total_expected = np.max(frame_arr) - np.min(frame_arr) + 1
    missing_count = total_expected - frame_len
    
    if missing_count > 0:
        return  missing_count, frame_len+missing_count, frame_len
    
    return dropped_frame_count, total_frames, current_frame


