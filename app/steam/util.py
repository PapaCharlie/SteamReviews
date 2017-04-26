from os import path
from app import dynamodb

data_dir = path.realpath(path.join(path.realpath(__file__), "..", "..", "..", "data"))
mallet_dir = path.realpath(path.join(path.realpath(__file__), "..", "..", "..", "mallet_output"))

def data_file(*path_segments):
    return path.join(data_dir, *path_segments)

def mallet_file(*path_segments):
    return path.join(mallet_dir, *path_segments)
