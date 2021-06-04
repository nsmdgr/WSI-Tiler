
import ray

from histolab.slide import Slide
from histolab.tiler import ScoreTiler
from histolab.masks import TissueMask
from histolab.scorer import NucleiScorer

import pathlib
import pandas as pd
import argparse
from tqdm import tqdm
import time
import sys

# helper used for progress bar logging
def to_iterator(obj_ids):
    while obj_ids:
        done, obj_ids = ray.wait(obj_ids)
        yield ray.get(done[0])

@ray.remote
def tile_wsi(wsi_path, tiles_dir, tile_size=512, tissue_percent=80., thumbnail_dir=None, score_report_dir=None):
    """Splits a single Whole-Slide-Image into tiles of size `tile_size`. 
       Tiles are filtered based on how much tissue is detected.

    Parameters
    ----------
    wsi_path :   pathlib.Path
        Path to the .svs file describing the WSI.
    tiles_dir : pathlib.Path
        Path to the directory where tiles are saved.
        Tiles are saved with the pattern {slide.name}_tile_{tiles_counter}_level{level}_{x_ul_wsi}-{y_ul_wsi}-{x_br_wsi}-{y_br_wsi}.png
        where `{x_ul_wsi, y_ul_wsi, x_br_wsi, y_br_wsi} describe the top-left and bottom-right pixel coordinates of the tile in the WSI.`
    tile_size : int
        Specifies the height and width of the square tiles. 
    tissue_percent : float
        Tiles where less than `tissue_percent` tissue is detected are rejected. 
    thumbnail_dir : pathlib.Path
        Path to directory where tiler thumbnails are saved.
    score_report_dir : pathlib.Path
        Path to directory where score reports are saved as csv. 
        For a given WSI, the score report contains URIs to the resulting tiles associated with a combined Nuclei-Tissue-Detection score. 
    Returns
    -------
    Tuple containing WSI_ID, WSI_URI and String indicating success or failure (used for final status reports).
    """
    
    try:
        
        slide = Slide(wsi_path, tiles_dir)
        
        tiler = ScoreTiler(
            scorer = NucleiScorer(),
            tile_size=(tile_size, tile_size),
            n_tiles = 0, # all tiles
            level=0,     # highest resolution
            check_tissue=True,
            tissue_percent=tissue_percent,
            pixel_overlap=0, 
            prefix=f"{slide.name}_",
            suffix=".png"
        )
        
        tissue_mask = TissueMask()
        
        tiler.extract(
            slide, 
            tissue_mask, 
            report_path=score_report_dir/f'{slide.name}_score_report.csv', 
            thumbnail_path=thumbnail_dir/f'{slide.name}_thumbnail.png'
        )
        
        return (wsi_path.stem, wsi_path, 'success')

    except:
        
        return (wsi_path.stem, wsi_path, 'fail')


if __name__ == '__main__':
    
    start_time = time.time()
    
    parser = argparse.ArgumentParser(description='Split Whole-Slide-Images into a set of smaller tiles.')
    
    parser.add_argument('wsi_dir',          help='(Possibly nested) directory containing input WSIs.',         type=pathlib.Path)
    parser.add_argument('out_dir',          help='Directory for tiles, reports, thumbnails, ray logs.',        type=pathlib.Path)
    parser.add_argument('--tile_size',      help='Specifies height and width of the resulting square tiles.',  type=int,   default=512)
    parser.add_argument('--tissue_percent', help='Reject tiles containing less then `tissue_percent` tissue.', type=float, default=80.)
    
    args = parser.parse_args()

    if not args.wsi_dir or not args.out_dir:
        sys.exit('No WSIs found in `wsi_dir`. Exiting...')      

    # create output directories
    tiles_dir        = args.out_dir/'tiles'
    score_report_dir = args.out_dir/'score_reports'
    thumbnail_dir    = args.out_dir/'tiler_thumbnails'

    for directory in [tiles_dir, score_report_dir, thumbnail_dir]:
        if not directory.exists():
            directory.mkdir(parents=True)

    # get paths to all input WSIs
    wsi_paths = list(args.wsi_dir.rglob('*.svs'))
    if not wsi_paths:
        sys.exit('No WSIs found in `wsi_dir`. Exiting...')

    # start parallel tiling
    ray.init(log_to_driver=False,  include_dashboard=False, _temp_dir='/tmp/histo_tiler_ray_logs')

    results = []
    for wsi_path in wsi_paths[:20]: #TODO remove [:5]
        results.append(
            tile_wsi.remote(
                wsi_path=wsi_path, 
                tiles_dir=tiles_dir, 
                tile_size=args.tile_size,
                tissue_percent=args.tissue_percent, 
                thumbnail_dir=thumbnail_dir, 
                score_report_dir=score_report_dir
            )
        )

    print('-'*19)
    print('---  WSI Tiler  ---')
    print('-'*19, end='\n'*2)
    print('-'*100)
    print(f'{"Input WSI Dir:":<17} {args.wsi_dir}')
    print(f'{"Tiles Dir:":<17} {tiles_dir}')
    print(f'{"Score Report Dir:":<17} {score_report_dir}')
    print(f'{"Thumbnail Dir:":<17} {thumbnail_dir}')
    print('-'*100, end='\n'*2)
    print('WSI Tiling...', end='\n'*2)
    
    # progress bar
    [_ for _ in tqdm(to_iterator(results), total=len(results))]
    
    # save status file of run
    results = ray.get(results)
    results = pd.DataFrame(results, columns=['Slide_ID', 'Slide_URI', 'Status'])
    results.to_csv(args.out_dir/'slide_status.csv', index=False)
    
    # log elapsed time
    print('\n')
    print('-'*35)
    print(f'Tiler finished after {(time.time() - start_time)/60:.1f} minutes.')
    print('-'*35)