# WSI-Tiler

Very simple, parallel Whole-Slide-Imaging Tiler for Digital Histopathology built using histolab and ray.

## Install

```
conda create -n wsi_env python=3.8
conda activate wsi
pip install -r requirements.txt
```

## Usage

```
python wsi_tiler.py -h
```

```
usage: wsi_tiler.py [-h] [--tile_size TILE_SIZE] [--tissue_percent TISSUE_PERCENT] wsi_dir out_dir

Split Whole-Slide-Images into a set of smaller tiles.

positional arguments:
  wsi_dir               (Possibly nested) directory containing input WSIs.
  out_dir               Directory for tiles, reports, thumbnails, ray logs.

optional arguments:
  -h, --help            show this help message and exit
  --tile_size TILE_SIZE
                        Specifies height and width of the resulting square tiles.
  --tissue_percent TISSUE_PERCENT
                        Reject tiles containing less then `tissue_percent` tissue.
```
