
#!/usr/bin/env python3

"""
Useful/convenient custom extensions of Python's dictionary class.
Greg Conan: gregmconan@gmail.com
Created: 2025-01-23
Updated: 2025-01-24
"""
# Import standard libraries
from collections import defaultdict, UserDict
import pdb
from typing import (Any, Callable, Dict, Hashable, Iterable, List,
                    Mapping, Optional, SupportsBytes, Tuple)

# Import third-party PyPI libraries
from cryptography.fernet import Fernet

# Import local custom libraries
try:
    from utilities import (Bytesifier, Debuggable, noop)
except ModuleNotFoundError:
    from emailbot.utilities import (Bytesifier, Debuggable, noop)


class AttributeDict(defaultdict):  # TODO Remove this class?
    # From https://stackoverflow.com/a/41274937
    def __init__(self):
        super(AttributeDict, self).__init__(AttributeDict)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value


class LazyDict(UserDict):
    """
    Dict that can get/set items and ignore the 'default=' code until/unless \
    that code is needed, ONLY evaluating it after failing to get/set an \
    existing key. Benefit: The 'default=' code does not need to be valid \
    (yet) if self already has the key. You can pass a function to a "lazy" \
    method that only needs to work if a value is missing.
    Extended LazyButHonestDict from https://stackoverflow.com/q/17532929
    Keeps most core functionality of the Python dict type. 
    """

    def lazyget(self, key: Hashable, get_if_absent: Callable = noop,
                getter_args: Iterable = list(),
                getter_kwargs: Mapping = dict()) -> Any:
        """
        Return the value for key if key is in the dictionary, else return \
        the result of calling the 'default' parameter.
        LazyButHonestDict.lazyget from stackoverflow.com/q/17532929

        :param key: Object (hashable) to use as a dict key
        :param get_if_absent: function that returns the default value
        """
        return self[key] if self.get(key) is not None else \
            get_if_absent(*getter_args, **getter_kwargs)

    def lazysetdefault(self, key: Hashable, get_if_absent: Callable = noop,
                       getter_args: Iterable = list(),
                       getter_kwargs: Mapping = dict()) -> Any:
        """
        Return the value for key if key is in the dictionary; else add that \
        key to the dictionary, set its value to the the result of calling \
        the 'default' parameter with args & kwargs, then return that result.
        LazyButHonestDict.lazysetdefault from stackoverflow.com/q/17532929 

        :param key: Object (hashable) to use as a dict key
        :param get_if_absent: function that sets & returns the default value
        :param args: Unpacked Iterable[Any] of get_if_absent arguments
        :param kwargs: Unpacked Mapping[Any] of get_if_absent keyword arguments
        """
        if self.get(key) is None:
            self[key] = get_if_absent(*getter_args, **getter_kwargs)
        return self[key]


class LazyDotDict(LazyDict):  # defaultdict
    """
    LazyDict with dot.notation access to its items. It can get/set items...
    ...as object-attributes: self.item is self['item']. Benefit: You can \
       get/set items by using '.' or by using variable names in brackets.
    ...and ignore the 'default=' code until it's needed, ONLY evaluating it \
       after failing to get/set an existing key. Benefit: The 'default=' \
       code does not need to be valid (yet) if self already has the key.
    Adapted from answers to https://stackoverflow.com/questions/2352181 and \
    combined with LazyButHonestDict from https://stackoverflow.com/q/17532929
    Keeps most core functionality of the Python dict type.
    TODO: Right now, trying to overwrite a LazyDict method or a core dict \
          attribute will silently fail: the new value can be accessed through \
          dict methods but not as an attribute. Maybe worth fixing eventually?
    """
    # Allow dot.notation item access. From https://stackoverflow.com/a/23689767
    # and https://stackoverflow.com/questions/2352181#comment139381442_23689767
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    # Enable tab-completion of dotdict items. From
    # https://stackoverflow.com/questions/2352181#comment114004924_23689767
    __dir__ = dict.keys

    def __init__(self, *args, **kwargs):
        # From https://stackoverflow.com/a/41274937
        # super(LazyDotDict, self).__init__(LazyDotDict)
        super().__init__(*args, **kwargs)
        self.autodotdictify()

    def __getstate__(self):
        """Required for pickling. From https://stackoverflow.com/a/36968114"""
        return self

    def __setstate__(self, state):
        """Required for pickling. From https://stackoverflow.com/a/36968114

        :param state: _type_, _description_
        """
        self.update(state)
        self.__dict__ = self

    def autodotdictify(self):
        """Recursively transform every dict contained inside this dotdict \
        into a dotdict itself, ensuring nested dot access to dict attributes.
        From https://gist.github.com/miku/dc6d06ed894bc23dfd5a364b7def5ed8
        """
        for k, v in self.items():
            if isinstance(v, dict):  # TODO No, isinstance(v, Mapping) ?
                # TODO No, __class__(v) or __init__(v)?
                self[k] = LazyDotDict(v)

    def lookup(self, dotkey: str) -> Hashable:
        """Lookup value in a nested structure with a single key, e.g. `a.b.c`
        From https://gist.github.com/miku/dc6d06ed894bc23dfd5a364b7def5ed8
        """
        path = list(reversed(dotkey.split(".")))
        v = self
        while path:
            key = path.pop()
            if isinstance(v, dict):
                v = v[key]
            elif isinstance(v, list):
                v = v[int(key)]
            else:
                raise KeyError(key)
        return v


class Promptionary(LazyDict, Debuggable):
    """LazyDict that can interactively prompt the user to fill missing values."""

    def __init__(self, *args, debugging: bool = False, **kwargs) -> None:
        # This class can pause and debug when an exception occurs
        self.debugging = debugging
        super().__init__(*args, **kwargs)

    def get_or_prompt_for(self, key: str, prompt_fn: Callable,
                          prompt: str) -> Any:
        """Given a key, return the value mapped to it if one already exists; \
        otherwise prompt the user to interactively provide it and return that.

        :param key: str mapped to the value to retrieve
        :param prompt_fn: Callable, function to interactively prompt the \
                          user to provide the value, such as `input` or \
                          `getpass.getpass`
        :param prompt: str to display when prompting the user.
        :return: Any, the value mapped to key if one exists, else the value \
                 that the user interactively provided
        """
        return self.lazyget(key, prompt_fn, [prompt])

    def setdefault_or_prompt_for(self, key: str, prompt_fn: Callable,
                                 prompt: str) -> Any:
        """Given a key, return the value mapped to it if one already exists; \
        otherwise prompt the user to interactively provide it, store the \
        provided value by mapping it to key, and return that value.

        :param key: str mapped to the value to retrieve
        :param prompt_fn: Callable, function to interactively prompt the \
                          user to provide the value, such as `input` or \
                          `getpass.getpass`
        :param prompt: str to display when prompting the user.
        :return: Any, the value mapped to key if one exists, else the value \
                 that the user interactively provided
        """
        return self.lazysetdefault(key, prompt_fn, [prompt])


class Cryptionary(Promptionary, Bytesifier):  # , Debuggable
    """Extended LazyDict that automatically encrypts values before storing \
    them and automatically decrypts values before returning them. Created to \
    store user credentials slightly more securely, and reduce the likelihood \
    of accidentally exposing them."""

    def __init__(self, *args, debugging: bool = False, **kwargs):
        try:
            # Create encryption mechanism
            self.encrypted = set()
            self.crypt_key = Fernet.generate_key()
            self.cryptor = Fernet(self.crypt_key)

            # This class can pause and debug when an exception occurs
            super().__init__(*args, debugging=debugging, **kwargs)
        except TypeError as e:
            self.debug_or_raise(e, locals())

    def __getitem__(self, dict_key: Hashable) -> Any:
        """ `x.__getitem__(y)` <==> `x[y]` 

        :param dict_key: Hashable, key mapped to the value to retrieve
        :return: Any, the decrypted value mapped to dict_key
        """
        try:
            retrieved = super().__getitem__(dict_key)
            if retrieved is not None:
                retrieved = self.cryptor.decrypt(retrieved).decode("utf-8")
            return retrieved
        except (KeyError, TypeError) as e:
            self.debug_or_raise(e, locals())

    def __setitem__(self, dict_key: Hashable,
                    dict_value: SupportsBytes) -> None:
        """Set self[dict_key] to dict_value after encrypting dict_value.

        :param dict_key: Hashable, key mapped to the value to retrieve
        :param dict_value: SupportsBytes, _description_
        :return: _type_, _description_
        """
        if self.can_bytesify(dict_value):
            dict_value = self.cryptor.encrypt(self.bytesify(dict_value))
            self.encrypted.add(dict_key)
        return super().__setitem__(dict_key, dict_value)

    def __delitem__(self, key: Hashable) -> None:
        """Delete self[key]. 

        :param key: Hashable, key to delete and to delete the value of.
        :return: None
        """
        self.encrypted.discard(key)
        return super().__delitem__(key)
