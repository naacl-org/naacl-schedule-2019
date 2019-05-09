#!/usr/bin/env python3

"""
This script extracts the files that are needed to generate
the website and app schedules from the data files provided
by the NAACL 2019 pub chairs.

The files extracted by this script are as follows, under the given
output directory:

- `xml/{N19,W19,S19}.xml`, the XML files containing the author metadata,
  abstract, and anthology links for all papers being presented at
  the conference, workshops, and other co-located events.

- `order/*_order` files for the tracks, workshops and co-located events.

- `mapping/*_id_map.txt` files for the tracks, workshops and co-located events.

"""

import argparse
import logging
import tarfile

from os import makedirs
from pathlib import Path
from shutil import copy, move, rmtree


def main():

    # set up an argument parser
    parser = argparse.ArgumentParser(prog='extract_data.py')
    parser.add_argument('input_dir',
                        type=Path,
                        help="The input directory containing "
                             "the XML files as well as the tarballs for all "
                             "sessions and workshops in the conference. "
                             "This directory will be provided by the pub "
                             "chairs.")
    parser.add_argument('output_dir',
                        type=Path,
                        help="The output directory under which the extracted "
                             "files will be saved")

    # parse given command line arguments
    args = parser.parse_args()

    # set up the logging
    logging.basicConfig(format='%(message)s', level=logging.INFO)

    # create the various output directories we need
    logging.info('Creating output directories ...')
    xml_dir = args.output_dir / 'xml'
    order_dir = args.output_dir / 'order'
    mapping_dir = args.output_dir / 'mapping'
    for dir_name in [args.output_dir, xml_dir, order_dir, mapping_dir]:
        makedirs(dir_name, exist_ok=True)

    # now copy them over from the input to to the output directory
    logging.info('Copying XML files ...')
    for filename in ['N19.xml', 'W19.xml', 'S19.xml']:
        filepath = args.input_dir / filename
        copy(filepath, xml_dir)

    # next extract the order files from each of the tarballs under `data`
    logging.info('Extracting order and mapping files ...')
    num_tarballs = 0
    for tarpath in args.input_dir.glob('*_data.tgz'):
        num_tarballs += 1
        prefix = tarpath.name.split('_')[0]
        logging.info(' {}'.format(prefix))
        subpath = 'data/{}/proceedings'.format(prefix)
        with tarfile.open(tarpath, 'r:gz') as datafh:
            datafh.extractall(path=args.output_dir,
                              members=[datafh.getmember('{}/order'.format(subpath)),
                                       datafh.getmember('{}/id_map.txt'.format(subpath))])

    # move the extracted files into the right sub-directories
    logging.info('Re-organizing files ...')
    for session_dir in (args.output_dir / 'data').iterdir():
        move(session_dir / 'proceedings' / 'order',
             order_dir / '{}_order'.format(session_dir.name))
        move(session_dir / 'proceedings' / 'id_map.txt',
             mapping_dir / '{}_id_map.txt'.format(session_dir.name))

    # make sure we have the expected number of files
    assert len(list(xml_dir.glob('*.xml'))) == 3
    # we need to add 1 for the manual files
    assert len(list(order_dir.glob('*_order'))) == num_tarballs + 1
    assert len(list(mapping_dir.glob('*_id_map.txt'))) == num_tarballs + 1

    # delete the extracted directory
    rmtree(args.output_dir / 'data')


if __name__ == '__main__':
    main()
