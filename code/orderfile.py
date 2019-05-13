import re

from datetime import datetime

_METADATA_REGEXP = re.compile(r'%([^\s]+)\s+([^%]+)')


def parse_metadata_into_dict(metadata_string):
    """
    A function to parse any additional metadata
    provided as part of a session or item in the
    order file. This metadata usually contains the
    room and the session chair. An example of such a
    metadata string is:
    "# %room FOO %chair1 BAR BAZ"

    This function parses such a string and creates
    a dictionary from it irrespective of the specified
    metadata categories. For example, for the above
    string, the output is the dictionary:

    {'room': 'FOO', 'chair1': 'BAR BAZ'}

    Parameters
    ----------
    metadata_string : str
        The metadata string for a session.

    Returns
    -------
    metadata_dict : dict
        A dictionary containing the metadata keys
        and values.
    """
    metadata_string = metadata_string.strip()
    return dict(_METADATA_REGEXP.findall(metadata_string))


class Agenda(object):
    """
    Class encapsulating an Agenda object which is defined
    as a collection of `Day` objects.
    """
    def __init__(self):
        super(Agenda, self).__init__()
        self.days = []

    def update_states(self,
                      current_tuple,
                      save_session=True,
                      save_group=True,
                      save_day=True):
        """
        A method run when we transition to a new state
        in the state machine we are using to keep track
        of progress through the order file. For example,
        at transition time, we want to save any active
        sessions to either the currently active session
        group (if it's a parallel track) or the currently
        active day, if it's a plenary session. This method
        updates the objects passed in via reference directly
        and does not return anything.

        Parameters
        ----------
        current_tuple : (Day, SesssionGroup, Session, Item)
            A tuple containing the currently active
            `Day` object, the currently active `SessionGroup`
            object (if any), the currently active
            `Session` object (if any), and the current
            active `Item` object (if any). These objects
            are passed in via reference and updated directly
            by this method.
        save_session : bool, optional
            A boolean indicating whether to save the
            currently active `Session` to either the
            session group or the day (depending on the type)
            of session), effectively being done with it.
            This may not always be necessary, e.g., when
            we are not done moving through the items in a
            a single session.
        save_group : bool, optional
            A boolean indicating whether to save the
            currently active `SessionGroup` object to
            the currently active `Day` object, effectively
            being done with it. This may not always be
            necessary, e.g., when we are not done moving
            through the parallel tracks in a single session
            group.
        save_day : bool, optional
            A boolean indicating whether to save the currently
            active `Day` object to the `Agenda`, effectively being
            done with it. This is not always necessary, e.g.,
            when the day is not yet finished.
        """
        (current_day,
         current_session_group,
         current_session,
         current_item) = current_tuple

        # if there is an active item ...
        if current_item:

            # add it to the active session
            if current_session:
                current_session.add(current_item)

        # if there is an active session ....
        if save_session and current_session:

            # add it to the active session group
            # if any (unless it's a plenary/break session);
            if (current_session_group and
                    current_session.type not in ['plenary', 'break']):
                    current_session_group.add(current_session)

            # otherwise add it to the active day
            else:
                current_day.add(current_session)

        # save the currently active session group, if
        # any, to the active day
        if save_group and current_session_group:
            current_day.add(current_session_group)

        # save the active day to the agenda
        if save_day:
            self.days.append(current_day)

    def fromfile(self, filepath):
        """
        A method to create an `Agenda` object from
        a given order file.

        Parameters
        ----------
        filepath : str
            The path to the order file that we want
            to convert to an `Agenda` object.
        """
        current_day = None
        current_session_group = None
        current_session = None
        current_item = None
        with open(filepath, 'r') as orderfh:
            for line in orderfh:
                line = line.strip()
                if not line:
                    continue

                # if we encounter a new day ..
                if line.startswith('* '):

                    # update the various pending states
                    if current_day:
                        self.update_states((current_day,
                                            current_session_group,
                                            current_session,
                                            current_item))

                    # once the update is finished; no sessions
                    # and session groups can be active for the
                    # new day since we just started it
                    current_session = None
                    current_session_group = None
                    current_item = None

                    # make this new day the active one
                    current_day = Day.fromstring(line)

                # if we encounter a new plenary session ...
                elif line.startswith('! '):

                    # update the various pending states
                    self.update_states((current_day,
                                        current_session_group,
                                        current_session,
                                        current_item), save_day=False)

                    # make it so that there is no group active anymore
                    # since session groups cannot span plenary sessions
                    current_session_group = None
                    current_item = None

                    # make this new plenary session the active one
                    current_session = Session.fromstring(line)

                # if we encounter a new session group ...
                elif line.startswith('+ '):

                    self.update_states((current_day,
                                        current_session_group,
                                        current_session,
                                        current_item), save_day=False)

                    # there is no longer an active session
                    # or an active item
                    current_session = None
                    current_item = None

                    # make this new session group the active one
                    current_session_group = SessionGroup.fromstring(line)

                # if we encounter a new paper/poster/tutorial/best-paper
                # session ...
                elif line.startswith('= '):

                    # update states but do not yet save
                    # the currently active session group
                    # since we may still be in it
                    self.update_states((current_day,
                                        current_session_group,
                                        current_session,
                                        current_item),
                                       save_day=False,
                                       save_group=False)

                    current_item = None

                    # make this new session the active one
                    current_session = Session.fromstring(line)

                # if we encounter a poster group topic ...
                elif line.startswith('@ '):

                    # update the states for pending items
                    # but do not yet save the day, the session
                    # group or the session since we are still
                    # in them
                    self.update_states((current_day,
                                        current_session_group,
                                        current_session,
                                        current_item),
                                       save_day=False,
                                       save_group=False,
                                       save_session=False)

                    # save the topic to greedily attach to
                    # the next poster we see, which should
                    # be the next line
                    current_poster_topic = line.lstrip('@ ').rstrip()
                    current_item = None

                # if we encounter a presentation item
                # (poster/paper/tutorial) ...
                elif Item._regexp.match(line):

                    # if we have encountered a poster and
                    # we have an active poster topic, attach
                    # that topic to this poster to indicate
                    # that this is where the topic starts
                    # and then remove the active topics since
                    # we are done with it
                    if current_item and current_item.type == 'poster':
                        current_item.topic = current_poster_topic
                        current_poster_topic = None

                    # update the states for pending items
                    # but do not yet save the day, the session
                    # group or the session since we may still
                    # be in them
                    self.update_states((current_day,
                                        current_session_group,
                                        current_session,
                                        current_item),
                                       save_session=False,
                                       save_day=False,
                                       save_group=False)

                    # make this new item the currently active one
                    matchobj = Item._regexp.match(line)
                    current_item = Item.fromstring(matchobj, current_session.type)

            # after we are done iterating through the
            # lines in the file, we may still have some
            # pending items, sessions, groups, and days
            # to take care of before we are done
            self.update_states((current_day,
                                current_session_group,
                                current_session,
                                current_item))

            # now we are really done and so we can
            # nullify the current pointers since
            # they are no longer needed
            current_day = None
            current_session_group = None
            current_session = None
            current_item = None


class Day(object):
    """
    Class encapsulating a day in the order file.
    A `Day` object contains a datetime attribute
    along a list (`contents`) that can contain
    sessions (represented as `Session` objects)
    amd session groups (represented as `SessionGroup`
    objects) happening on that day.
    """
    def __init__(self, datetime):
        super(Day, self).__init__()
        self.datetime = datetime
        self.contents = []

    def __str__(self):
        return self.datetime.strftime('%A, %B %d, %Y')

    def __repr__(self):
        return 'Day <{}>'.format(str(self))

    @classmethod
    def fromstring(cls, day_string):
        """
        A class method to create a `Day` instance from
        a string indicating a day in the order file.

        Parameters
        ----------
        day_string : str
            A string indicating the day in the order
            file. An example string looks like this:
            "Monday, June 2, 2019".

        Returns
        -------
        day : Day
            An instance of `Day`.
        """
        real_day_string = day_string.lstrip('* ').rstrip()
        return cls(datetime.strptime(real_day_string, '%A, %B %d, %Y'))

    def add(self, session_or_session_group):
        """
        A method to add a `Session` or `SessionGroup`
        object to this day.

        Parameters
        ----------
        session_or_session_group : Session or SessionGroup
            An instance of either `Session` or `SessionGroup`.
        """
        self.contents.append(session_or_session_group)


class SessionGroup(object):
    """
    Class encapsulating a session group containing parallel
    tracks in the order file. A `SessionGroup` object is
    defined by a title, a list of the sessions that it
    contains (represented as `Session` objects), a start
    time, and an end time.
    """
    _regexp = re.compile(r'([0-9]{1,2}:[0-9]{2})--([0-9]{1,2}:[0-9]{2})\s+(.*)')

    def __init__(self, title='', start_time='', end_time=''):
        super(SessionGroup, self).__init__()
        self.title = title
        self.sessions = []
        self.start = start_time
        self.end = end_time

    @classmethod
    def fromstring(cls, session_group_string):
        """
        A class method to create a `SessionGroup`
        object from a string in the order file.
        An example string looks like this:
        "11:00--12:30 Oral Sessions (long papers) and Posters"

        Parameters
        ----------
        session_group_string : str
            The string indicating a session group in
            the order file.

        Returns
        -------
        session_group : SessionGroup
            An instance of `SessionGroup`.
        """
        real_session_group_string = session_group_string.lstrip('+ ')
        (session_group_start,
         session_group_end,
         session_group_title) = cls._regexp.match(real_session_group_string).groups()
        return cls(title=session_group_title.strip(),
                   start_time=session_group_start.strip(),
                   end_time=session_group_end.strip())

    def add(self, session):
        """
        A method to add a session to this session group.

        Parameters
        ----------
        session : Session
            An instance of `Session`.
        """
        self.sessions.append(session)

    def __repr__(self):
        return 'SessionGroup {}--{} <{}>'.format(self.start,
                                                 self.end,
                                                 self.title)


class Session(object):
    """
    Class encapsulating a session in the order file.
    A `Session` object is defined by an ID (only
    for parallel tracks), a title, a type ("plenary",
    "break", "paper", "poster", "tutorial", or "best_paper"),
    a location (if any), a start time, an end time,
    and a session chair (if any).
    """

    _plenary_regexp = re.compile(r'! ([0-9]{1,2}:[0-9]{2})--([0-9]{1,2}:[0-9]{2})\s+([^#]+)#?([^#]+)?$')
    _paper_regexp = re.compile(r'= Session ([^:]+): ([^#]+)#?([^#]+)?$')
    _non_paper_regexp = re.compile(r'= ([^#]+)#?([^#]+)?$')

    def __init__(self,
                 session_id='',
                 title='',
                 type='',
                 location='',
                 start_time='',
                 end_time='',
                 chair=''):
        super(Session, self).__init__()
        self.id_ = session_id
        self.title = title
        self.type = type
        self.location = location
        self.chair = chair
        self.start = start_time
        self.end = end_time
        self.items = []

    def __repr__(self):
        out = 'Session '
        if self.start:
            out += '{}--{} '.format(self.start, self.end)
        attrs = ['type={}'.format(self.type)]
        if self.id_:
            attrs.append('id={}'.format(self.id_))
        if self.title:
            attrs.append('title={}'.format(self.title))
        if self.location:
            attrs.append('room={}'.format(self.location))
        if self.chair:
            attrs.append('chair={}'.format(self.chair))
        out += '<' + ', '.join(attrs) + '>'

        return out

    def add(self, item):
        self.items.append(item)

    @classmethod
    def fromstring(cls, session_string):
        """
        A class method to create a `Session` instance
        from a string in the order file. The format
        of the string depends on the type of session
        and a different regular expression is used
        to parse each different session type. Here
        are some examples:

        Break : "! 12:30--14:00 Lunch Break"
        Non-break Plenary : "! 9:30--10:30 Keynote 1: Arvind Narayanan "Data as a Mirror of Society: Lessons from the Emerging Science of Fairness in Machine Learning" # %room Nicollet Grand Ballroom"
        Paper : "= Session 1B: Speech # %room Nicollet A %chair1 Yang Liu"
        Poster : "= Session 1F: Question Answering, Sentiment, Machine Translation, Resources \& Evaluation (Posters) # %room Hyatt Exhibit Hall"

        Break and non-break plenary sessions are distinguished
        by the presence of the words "break/coffee/lunch". Paper
        and poster sessions are distinguished by the presence
        of the word "posters".

        Parameters
        ----------
        session_string : str
            The string indicating a session in
            the order file.

        Returns
        -------
        session : Session
            An instance of `Session`.
        """
        # plenary session or break
        if session_string.startswith('!'):
            (start,
             end,
             title,
             metadata) = cls._plenary_regexp.match(session_string).groups()
            metadata_dict = parse_metadata_into_dict(metadata) if metadata else {}

            session_type = 'break' if re.search(r'break|lunch|coffee', title.lower()) else 'plenary'

            return cls(title=title.strip(),
                       type=session_type,
                       location=metadata_dict.get('room', '').strip(),
                       chair=metadata_dict.get('chair1', '').strip(),
                       start_time=start.strip(),
                       end_time=end.strip())

        elif session_string.startswith('='):
            # paper session
            if session_string.startswith('= Session'):
                (id_,
                 title,
                 metadata) = cls._paper_regexp.match(session_string).groups()
                metadata_dict = parse_metadata_into_dict(metadata) if metadata else {}
                session_type = 'poster' if re.search('posters', title.lower()) else 'paper'
                return cls(session_id=id_.strip(),
                           title=title.strip(),
                           type=session_type,
                           location=metadata_dict.get('room', '').strip(),
                           chair=metadata_dict.get('chair1', '').strip())
            else:
                # either tutorial or best paper
                (title,
                 metadata) = cls._non_paper_regexp.match(session_string).groups()
                metadata_dict = parse_metadata_into_dict(metadata) if metadata else {}
                session_type = 'tutorial' if re.search('tutorial', title.lower()) else 'best_paper'
                return cls(title=title.strip(),
                           type=session_type,
                           location=metadata_dict.get('room', '').strip())


class Item(object):

    """
    Class encapsulating a presentation item in the
    order file. There are three main item types:
    papers, posters, and tutorials. Demo, SRW, and
    Industry items are all considered papers.
    An Item is defined by an ID, the `type` attribute
    ("paper", "poster", or "tutorial"), a title, authors,
    a track ("demos", "srw", or "industry"), a location
    (if any), a start time (if any), and an end time
    (if any).
    """

    _regexp = re.compile(r'^([0-9]+(-[a-z]+)?)(\s*([0-9]{1,2}:[0-9]{2})--([0-9]{1,2}:[0-9]{2}))?\s+#([^#]*)$')

    def __init__(self, id_, type, **kwargs):
        super(Item, self).__init__()
        self.id_ = id_
        self.type = type
        for key, value in kwargs.items():
            self.__setattr__(key, value)

    def __repr__(self):
        out = '{} <id={}, track={}'.format(self.type.title(),
                                           self.id_,
                                           self.track)
        if self.type == 'poster' and self.topic:
            out += ', topic={}>'.format(self.topic)
        else:
            out += '>'

        return out

    @classmethod
    def fromstring(cls,
                   item_regex_match_object,
                   containing_session_type):
        """
        A class method to create an `Item` instance
        from a string in the order file. The format
        of the string depends on the item type, whether
        it's a paper, poster, or tutorial. All of them
        start with a numeric ID (with a possible track
        indicator of some sort) and then have various
        other attributes. Examples include:

        Regular paper/poster item: "737 15:30--15:45  #"
        Tutorial : "28-tutorial 9:00--12:30  # %room Greenway DE/FG"
        A special track paper : "45-srw 15:30--15:45 #"

        Parameters
        ----------
        item_regex_match_object : re.MatchObject
            A match object returned by applying the
            `Item` regular expression to the string.
        containing_session_type : str
            A string indicating the type of the most recently
            active `Session` object. This lets us distinguish
            between posters and papers.

        Returns
        -------
        item : Item
            An instance of `Item`.
        """
        (item_id,
         _,
         _,
         start_time,
         end_time,
         metadata_string) = item_regex_match_object.groups()
        if containing_session_type == 'poster':
            return cls(item_id,
                       'poster',
                       topic='',
                       title='',
                       track='main',
                       authors='')
        elif (containing_session_type == 'paper' or
                containing_session_type == 'best_paper'):
            if '-' in item_id:
                real_id, id_type = item_id.split('-')
                item_id = real_id
            else:
                id_type = 'main'
            return cls(item_id,
                       'paper',
                       title='',
                       authors='',
                       track=id_type,
                       start=start_time,
                       end=end_time)
        elif containing_session_type == 'tutorial':
            real_id, id_type = item_id.split('-')
            metadata_dict = parse_metadata_into_dict(metadata_string)
            assert id_type == 'tutorial'
            return cls(real_id,
                       'tutorial',
                       track='main',
                       title='',
                       authors='',
                       location=metadata_dict.get('room', '').strip(),
                       start=start_time,
                       end=end_time)
