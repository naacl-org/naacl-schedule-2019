"""
A Python module to parse anthology XML files (and non-anthology
metadata TSV files, if available) to obtain authors, titles,
abstracts and, optionally, anthology URLs for papers and posters.
This code is entirely in service of producing web and app schedules
for conferences and, therefore, no other metadata is extracted.
In addition, for those papers that are in the non-anthology
metadata file, no abstracts and anthology URLs are available.

Author: Nitin Madnani (nmadnani@ets.org)
Date: May, 2019
"""

import csv

from collections import namedtuple
from pathlib import Path

from bs4 import BeautifulSoup

# define a named tuple that will contain the metadata for each item
MetadataTuple = namedtuple('MetadataTuple',
                           ['title', 'authors', 'abstract', 'anthology_url'])


class ScheduleMetadata(object):
    """
    Class encapsulating an object that contains
    the metadata needed for the website and app
    schedules. The object is defined by 3 dictionaries:
    one defined by the mapping file that maps IDs in the
    anthology XML files to the IDs in the various order files,
    the second is the same as the first but in the reverse
    direction, and the third maps IDs in the order files
    to tuples containing the following metadata: title,
    authors, abstracts, and anthology URLs.
    """
    def __init__(self, metadata_dict=None, mapping_dict=None):
        super(ScheduleMetadata, self).__init__()
        self._order_id_to_metadata_dict = metadata_dict
        self._order_id_to_anthology_id_dict = mapping_dict
        self._anthology_id_to_order_id_dict = {v: k for k, v in mapping_dict.items()}

    @classmethod
    def _parse_id_mapping_file(cls, mapping_file):
        """
        A private class method used to parse files
        mapping anthology IDs to IDs in the order files.
        These files are generally provided by the pub chairs.

        Parameters
        ----------
        mapping_file : str
            The path to the mapping file.

        Returns
        -------
        mapping_dict : dict
            A dictionary with order file IDs as the keys
            and anthology file IDs as the values.

        Raises
        ------
        FileNotFoundError
            If the mapping files does not exist.
        """

        # convert string to a Path object
        mapping_file = Path(mapping_file)

        # make sure the file exists
        if not mapping_file.exists():
            raise FileNotFoundError('File {} does not exist'.format(mapping_file))

        # iterate over each row of the file and populate
        # the dictionary we want to return
        mapping_dict = {}
        with open(mapping_file, 'r') as mappingfh:
            for line in mappingfh:
                anthology_id, order_id = line.strip().split(' ')
                mapping_dict[order_id] = anthology_id

        return mapping_dict

    @classmethod
    def _parse_anthology_xml(cls, xml_file):
        """
        A private class method used to parse the
        anthology XML files containing the metadata
        for each paper.

        Parameters
        ----------
        xml_file : str
            Path to the xml file to parse.

        Returns
        -------
        anthology_dict : dict
            A dictionary with the anthology ID from
            the XML file as the key and a `MetdataTuple`
            instance containing the corresponding
            metadata as the value.

        Raises
        ------
        FileNotFoundError
            If the xml file does not exist.
        """

        # initialize the output dictionary
        anthology_dict = {}

        # make sure the file exists
        xml_file = Path(xml_file)
        if not xml_file.exists():
            raise FileNotFoundError('File {} does not exist'.format(xml_file))

        # parse the XML file using BeautifulSoup and extract
        # the metadata items we need for each paper; note that
        # we do not care about which volume the paper is in
        with open(xml_file, 'r') as xmlfh:
            soup = BeautifulSoup(xmlfh, 'xml')
            for paper in soup.find_all('paper'):

                # get the anthology ID
                id_ = '{}-{}'.format(xml_file.stem, paper['id'])

                # get the paper title
                title = paper.title.text

                # get the abstract which may not exist for all papers
                abstract = '' if not paper.abstract else paper.abstract.text

                # get the paper's anthology URL
                anthology_url = paper.url.text

                # get the authors which also may not exist for all papers
                if paper.find_all('author'):
                    authortags = paper.find_all('author')
                    authorlist = ['{} {}'.format(author.first.text, author.last.text) for author in authortags]

                    # reformat author string:  "X, Y, Z" -> "X, Y and Z"
                    # for readability
                    authors = '{} and {}'.format(', '.join(authorlist[:-1]), authorlist[-1])
                else:
                    authors = ''

                # create the named tuple and save it in the dictionary
                anthology_dict[id_] = MetadataTuple(title=title,
                                                    authors=authors,
                                                    abstract=abstract,
                                                    anthology_url=anthology_url)

        # return the output dictionary
        return anthology_dict

    @classmethod
    def _parse_non_anthology_file(cls, non_anthology_tsv):
        """
        A private class method used to parse the
        non-anthology metadata TSV file containing
        the titles and authors for order file IDs.

        Parameters
        ----------
        non_anthology_tsv : str
            Path to non-anthology metadata TSV file.

        Returns
        -------
        non_anthology_dict : dict
            A dictionary with the order file IDs
            in the TSV file as the key and `MetadataTuple`
            instances as values, with only the `title`
            and `author` fields populated.

        Raises
        ------
        FileNotFoundError
            If the non-anthology TSV file does not exist.
        """
        # initialize the return dictionary
        non_anthology_dict = {}

        # make sure the file actually exists
        non_anthology_tsv = Path(non_anthology_tsv)
        if not non_anthology_tsv.exists():
            raise FileNotFoundError('File {} does not exist'.format(non_anthology_tsv))

        # iterate over each TSV row and create a new
        # MetadataTuple instance and add to dictionary
        with open(non_anthology_tsv, 'r') as nonanthfh:
            reader = csv.DictReader(nonanthfh,
                                    dialect=csv.excel_tab)
            for row in reader:
                title = row['title'].strip()
                authors = row['authors'].strip()
                value = MetadataTuple(title=title,
                                      authors=authors,
                                      abstract='',
                                      anthology_url='')
                key = row['paper_id'].strip()
                non_anthology_dict[key] = value

        # return the dictionary
        return non_anthology_dict

    @classmethod
    def fromfiles(cls,
                  xmls=[],
                  mappings=[],
                  non_anthology_tsv=None):
        """
        Class method to create an instance of
        `ScheduleMetadata` from the set of
        relevant files.

        Parameters
        ----------
        xmls : list, optional
            List of anthology XML files.
        mappings : list, optional
            List of ID mapping (`id_map.txt`) files.
        non_anthology_tsv : None, optional
            A TSV file containing author and title
            metdata for the order file IDs that are
            _not_ in the anthology XML files.

        Returns
        -------
        schedule_metadata : ScheduleMetadata
            A populated instance of `ScheduleMetadata`.
        """
        # initialize dictionaries we need for later
        order_id_to_anthology_id_dict = {}
        order_id_to_metadata_dict = {}
        anthology_metadata_dict = {}

        # parse the ID mapping files first and update the
        # relevant dictionary with the results
        for mapping in mappings:
            order_id_to_anthology_id_dict.update(cls._parse_id_mapping_file(mapping))

        # next parse all of the anthology XML files and update
        # the relevant dictionary with the results
        for xml in xmls:
            anthology_metadata_dict.update(cls._parse_anthology_xml(xml))

        # next create the bridge between the paper ID and
        # the anthology metadata
        for (order_id,
             anthology_id) in order_id_to_anthology_id_dict.items():
            order_id_to_metadata_dict[order_id] = anthology_metadata_dict[anthology_id]

        # next handle the non-anthology metadata TSV file
        # if one has been provided and update the
        # bridged dictionary
        if non_anthology_tsv:
            order_id_to_metadata_dict.update(cls._parse_non_anthology_file(non_anthology_tsv))

        # finally return an instance of ScheduleMetadata
        # with the dictionaries populated
        return cls(metadata_dict=order_id_to_metadata_dict,
                   mapping_dict=order_id_to_anthology_id_dict)

    def __getitem__(self, id_):
        """
        Look up metadata for an order file ID or an anthology ID.
        We infer whether the given ID is an anthology ID if it
        start with 'N', 'W', or 'S', since order file IDs
        always start with a number.

        Parameters
        ----------
        id_ : str
            Order file ID or anthology ID.

        Returns
        -------
        metadata_tuple : MetadataTuple
            An instance of `MetadataTuple` containing
            the metdata for the given ID.
        """
        if id_[0] in ['N', 'W', 'S']:
            order_id = self._anthology_id_to_order_id_dict[id_]
        else:
            order_id = id_
        return self._order_id_to_metadata_dict[order_id]
