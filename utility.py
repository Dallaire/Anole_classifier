import urllib.request
import tensorflow as tf
from sklearn.utils.class_weight import compute_class_weight
import pandas as pd
import numpy as np
import threading
import urllib
import os
import cv2
import re

#configs
taxa = [116461, 36514, 36488, 36391, 36455]
folder_path = 'F:/LizardCV'
file_path = 'F:/LizardCV/116461&36514.csv' #modify with file name

def download_images(filepath):
    df = pd.read_csv(filepath)
    for arr in np.array_split(df, 10):
        df = pd.DataFrame(arr)
        t = threading.Thread(target=download_images_part, args=(arr,))
        t.start()

def download_images_part(df):
    for index, row in df.iterrows():
        taxon_id = row['taxon_id']
        image_url = row['image_url']
        id = row['id']

        if not pd.isnull(image_url) and 'https://inaturalist-open-data.s3.amazonaws.com/photos' in image_url:
            save_path = f"{folder_path}/Raw/{taxon_id}_{id}.jpg"
            try:
                os.makedirs( os.path.dirname(save_path),exist_ok=True)
                if not os.path.isfile(save_path):
                    urllib.request.urlretrieve(image_url, save_path)
                
                image = tf.io.read_file(save_path)
                image = tf.image.decode_image(image, channels=3)
                image = tf.ensure_shape(image, [None, None, 3])
                image = tf.image.resize(image, [256, 256])
                image = image / 255.0  # Normalize to [0,1]
            except:
                print(save_path)
        if index%1000 == 0:
            print("In Progress")

def extract_label_from_filename(filename):
    # Example: if filename is 'cat_001.jpg', the label could be 'cat'
    return re.split('_|\.', filename)[0]

def load_and_preprocess_image(path, label):
    image = tf.io.read_file(path)
    image = tf.image.decode_image(image, channels=3)
    image = tf.ensure_shape(image, [None, None, 3])
    image = tf.image.resize(image, [256, 256])
    if image.shape != (256,256,3):
        print(path)
    image = image / 255.0  # Normalize to [0,1]
    label = tf.one_hot(label, depth=5)
    return image, label, path
    

def load_dataset_with_labels():
    # Path to the directory containing the images
    image_dir = folder_path + "/Raw2"

    # Get list of image file paths and their labels
    image_paths = []
    labels = []
    for filename in os.listdir(image_dir):
        if filename.endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(image_dir, filename)
            label = extract_label_from_filename(filename)
            image_paths.append(image_path)
            labels.append(label)
    
    # Create a DataFrame
    df = pd.DataFrame({'image_path': image_paths, 'label': labels})
    for index, row in df.iterrows():
        try:
            path = row['image_path']
            image = tf.io.read_file(path)
            image = tf.image.decode_image(image, channels=3)
            image = tf.ensure_shape(image, [None, None, 3])
            image = tf.image.resize(image, [256, 256])
            if image.shape != (256,256,3):
                print(f'Corrumpted Image: {path}')
            image = image / 255.0  # Normalize to [0,1]
        except:
            print(f'Corrumpted Image: {path}')
    # Map labels to integer indices
    label_names = sorted(set(labels))
    label_to_index = {label: index for index, label in enumerate(label_names)}
    df['label_index'] = df['label'].map(label_to_index)
    
    #Class weights
    class_weights = compute_class_weight('balanced', classes=np.unique(df['label_index']), y=df['label_index'])
    class_weight_dict = dict(enumerate(class_weights))

    #Create tensorflow dataset
    dataset = tf.data.Dataset.from_tensor_slices((df['image_path'].values, df['label_index'].values))
    dataset = dataset.map(load_and_preprocess_image, num_parallel_calls=tf.data.AUTOTUNE)
    print(dataset)
    # Batch and shuffle dataset
    batch_size = 32
    dataset = dataset.shuffle(buffer_size=1000)  # Adjust buffer size as needed
    dataset = dataset.batch(batch_size)
    
    return dataset, class_weight_dict

def train_test_split(dataset,train_pct):
    # Define the split ratio
    total_batches = len(dataset) 
    train_size = int(train_pct * total_batches)  
    train_dataset = dataset.take(train_size)
    test_dataset = dataset.skip(train_size)
    return train_dataset, test_dataset


#download_images(file_path)