#!/usr/bin/env python3

"""
Useful/convenient custom extensions of Python's dictionary class.
Greg Conan: gregmconan@gmail.com
Created: 2025-01-23
Updated: 2025-03-10
"""
# Import standard libraries
import pdb
from typing import (Any, Callable, Dict, Hashable, Iterable, List,
                    Mapping, SupportsBytes)

# Import third-party PyPI libraries
from cryptography.fernet import Fernet

# Import local custom libraries
try:
    from seq import Bytesifier, Xray
    from debugging import Debuggable, noop
except ModuleNotFoundError:
    from emailbot.seq import Bytesifier, Xray
    from emailbot.debugging import Debuggable, noop


class Explictionary(dict):
    """ dict that explicitly includes its class name in __repr__ """

    def __repr__(self) -> str:
        """ 
        :return: str, string representation of custom dict class including\
                 its class name: "CustomDict({...})"
        """
        return f"{self.__class__.__name__}({dict.__repr__(self)})"


class LazyDict(Explictionary):
    """
    Dict that can get/set items and ignore the 'default=' code until/unless \
    that code is needed, ONLY evaluating it after failing to get/set an \
    existing key. Benefit: The 'default=' code does not need to be valid \
    (yet) if self already has the key. If you pass a function to a "lazy" \
    method, then that function only needs to work if a value is missing.
    Extended LazyButHonestDict from https://stackoverflow.com/q/17532929
    Keeps most core functionality of the Python dict type. 
    """

    def lazyget(self, key: str, get_if_absent: Callable = noop,
                getter_args: Iterable = list(),
                getter_kwargs: Mapping = dict()) -> Any:
        """
        Return the value for key if key is in the dictionary, else return \
        the result of calling the `get_if_absent` parameter with args & \
        kwargs. Adapted from LazyButHonestDict.lazyget from \
        https://stackoverflow.com/q/17532929

        :param key: str to use as a dict key to map to value
        :param get_if_absent: function that returns the default value
        """
        return self[key] if self.get(key) is not None else \
            get_if_absent(*getter_args, **getter_kwargs)

    def lazysetdefault(self, key: str, get_if_absent: Callable = noop,
                       getter_args: Iterable = list(),
                       getter_kwargs: Mapping = dict()) -> Any:
        """
        Return the value for key if key is in the dictionary; else add that \
        key to the dictionary, set its value to the result of calling the \
        `get_if_absent` parameter with args & kwargs, then return that \
        result. Adapted from LazyButHonestDict.lazysetdefault from \
        https://stackoverflow.com/q/17532929 

        :param key: str to use as a dict key to map to value
        :param get_if_absent: Callable, function to set & return default value
        :param args: Unpacked Iterable[Any] of get_if_absent arguments
        :param kwargs: Unpacked Mapping[Any] of get_if_absent keyword arguments
        """
        if self.get(key) is None:
            self[key] = get_if_absent(*getter_args, **getter_kwargs)
        return self[key]


class DotDict(Explictionary):
    """
    dict with dot.notation access to its items. Compare `sklearn.utils.Bunch`.
    DotDict can get/set items as attributes: `self.item is self['item']`.
    Benefit: You can get/set items by using '.' or key names in brackets.
    Keeps most core functionality of the Python dict type.

    Adapted from answers to https://stackoverflow.com/questions/2352181 and\
    attrdict from https://stackoverflow.com/a/45354473 and dotdict from\
    https://github.com/dmtlvn/dotdict/blob/main/dotdict/dotdict.py
    """
    # Enable tab-completion of dotdict items. From
    # https://stackoverflow.com/questions/2352181#comment114004924_23689767
    __dir__ = dict.keys

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ensure that method names cannot be overwritten/deleted.
        # To ensure that custom dict attrs are set AS attrs instead of items,\
        # sets __protected_keywords__ relatively late to utilize is_ready_to.
        self.__protected_keywords__ = set(dir(__class__))

    def __delattr__(self, name: str) -> None:
        """ Implement `delattr(self, name)`.
        Deletes item (key-value pair) or attribute.

        :param name: str naming the attribute of self to delete.
        """
        if self.is_ready_to("delete", name):
            self.__delitem__(name)
        else:
            dict.__delattr__(self, name)

    def __getattr__(self, name: str) -> Any:
        """ `__getattr__(self, name) == getattr(self, name) == self.<name>`
        If name is not protected, then `self.<key> == self[key]`

        Effectively the same as `__getattr__ = dict.__getitem__` except that\
        `hasattr(self, <not in dict>)` works; it does not raise a `KeyError`.

        :param name: str naming the attribute/element of self to return.
        :raises AttributeError: if name is not an item or attribute of self.
        :return: Any, `getattr(self, name)` and/or `self[name]`
        """
        try:  # First, try to get an attribute (e.g. a method) of this object
            return dict.__getattribute__(self, name)
        except AttributeError as err:

            try:  # Next, get a value mapped to the key, if any
                return dict.__getitem__(self, name)

            # If neither exists, then raise AttributeError
            except KeyError:  # Don't raise KeyError; it breaks hasattr
                raise err from None  # Only show 1 exception in the traceback

    def __getstate__(self):
        """Required for pickling. From https://stackoverflow.com/a/36968114"""
        return self

    def __setattr__(self, name: str, value: Any) -> None:
        """ Implement `setattr(self, name, value)` and/or `self[name] = value`

        :param name: str naming the attribute/key to map the value to
        :param value: Any, the value of the new attribute/item
        """
        if self.is_ready_to("overwrite", name):
            self.__setitem__(name, value)
        else:
            dict.__setattr__(self, name, value)

    def __setitem__(self, key: str, value: Any) -> None:
        """ Set self[key] to value.

        :param key: str naming the key to map the value to
        :param value: Any, the value of the new item
        """
        if self.is_ready_to("overwrite", key):
            super().__setitem__(key, value)
        else:
            dict.__setitem__(self, key, value)

    def __setstate__(self, state):
        """Required for pickling. From https://stackoverflow.com/a/36968114

        :param state: _type_, _description_
        """
        self.update(state)
        self.__dict__ = self

    def autodotdictify(self, replace: type = dict):
        """ Recursively transform every dict contained inside this DotDict \
        into a DotDict itself, ensuring nested dot access to dict attributes.
        From https://gist.github.com/miku/dc6d06ed894bc23dfd5a364b7def5ed8

        :param replace: type of element/child/attribute to change to DotDict.
        """
        for k, v in self.items():
            if isinstance(v, replace) and not isinstance(v, self.__class__):
                self[k] = self.__class__(v)

    def is_ready_to(self, alter: str, attribute_name: str) -> bool:
        """ Check whether a given attribute of self is protected, if it's\
        alterable, or if self is still being initialized.

        :param alter: str, description of the alteration
        :param attribute_name: str, name of the attribute of self to alter
        :raises AttributeError: if the attribute is protected
        :return: bool, True if the attribute is not protected;\
                 False if self is still being initialized; else raise err
        """
        is_protected = False
        try:
            assert attribute_name in \
                dict.__getattribute__(self, "__protected_keywords__")
            is_protected = True
        except AttributeError:  # Still initializing self => not ready yet
            return False
        except AssertionError:  # Attribute is not protected => ready to alter
            return True
        if is_protected:  # Attribute is protected => can't alter; raise error
            raise AttributeError(f"Cannot {alter} read-only "
                                 f"'{self.__class__.__name__}' object "
                                 f"attribute '{attribute_name}'")


class LazyDotDict(DotDict, LazyDict):
    """
    LazyDict with dot.notation access to its items. It can get/set items...

    ...as object-attributes: `self.item is self['item']`. Benefit: You can \
       get/set items by using '.' or by using variable names in brackets.

    ...and ignore the `default=` code until it's needed, ONLY evaluating it \
       after failing to get/set an existing key. Benefit: The `default=` \
       code does not need to be valid (yet) if self already has the key.

    Adapted from answers to https://stackoverflow.com/questions/2352181 and \
    attrdict from https://stackoverflow.com/a/45354473 and dotdict from\
    https://github.com/dmtlvn/dotdict/blob/main/dotdict/dotdict.py and then\
    combined with LazyButHonestDict from https://stackoverflow.com/q/17532929

    Keeps most core functionality of the Python dict type.
    """
    ...


class Promptionary(LazyDict, Debuggable):
    """LazyDict that can interactively prompt the user to fill missing values.
    """

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
        """ Given a key, return the value mapped to it if one already exists;\
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


class Cryptionary(Promptionary, Bytesifier):
    """ Extended LazyDict that automatically encrypts values before storing \
    them and automatically decrypts values before returning them. Created to \
    store user credentials slightly more securely, and reduce the likelihood \
    of accidentally exposing them."""

    def __init__(self, from_map: Mapping = dict(),
                 debugging: bool = False, **kwargs):
        try:
            # Create encryption mechanism
            self.encrypted = set()
            self.cryptor = Fernet(Fernet.generate_key())

            # This class can pause and debug when an exception occurs
            super().__init__(debugging=debugging)

            # Encrypt every value in the input mapping(s)/dict(s)
            for prev_mapping in from_map, kwargs:
                for k, v in prev_mapping.items():
                    self[k] = v

        except TypeError as e:
            self.debug_or_raise(e, locals())

    def __getitem__(self, dict_key: Hashable) -> Any:
        """ `x.__getitem__(y)` <==> `x[y]` 

        :param dict_key: Hashable, key mapped to the value to retrieve
        :return: Any, the decrypted value mapped to dict_key
        """
        try:
            retrieved = dict.__getitem__(self, dict_key)
            if retrieved is not None:
                retrieved = self.cryptor.decrypt(retrieved).decode("utf-8")
            return retrieved
        except (KeyError, TypeError) as e:
            self.debug_or_raise(e, locals())

    def __setitem__(self, dict_key: str,
                    dict_value: SupportsBytes) -> None:
        """ Set self[dict_key] to dict_value after encrypting dict_value.

        :param dict_key: str, key mapped to the value to retrieve.
        :param dict_value: SupportsBytes, value to encrypt and store.
        :return: None
        """
        try:
            if self.can_bytesify(dict_value):
                dict_value = self.cryptor.encrypt(self.bytesify(dict_value))
                self.encrypted.add(dict_key)
            return super(Cryptionary, self).__setitem__(dict_key, dict_value)
        except AttributeError as err:
            self.debug_or_raise(err, locals())

    def __delitem__(self, key: str) -> None:
        """ Delete self[key]. 

        :param key: str, key to delete and to delete the value of.
        """
        self.encrypted.discard(key)
        del self[key]


class DotCryptionary(Cryptionary, LazyDotDict):  # NOTE: This may be useless
    def __init__(self, *args, debugging: bool = False, **kwargs):
        super().__init__(*args, debugging=debugging, **kwargs)
