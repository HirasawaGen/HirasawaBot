from typing import MutableMapping, Mapping
from typing import Any
from copy import deepcopy
from functools import update_wrapper
from abc import abstractmethod

from collections import defaultdict, OrderedDict, ChainMap



type LabeledTuple[*Ts] = tuple[str, *Ts]
type ObjOrCls[T] = T | type[T]


#ABC class
class NullSafeMapping[T](Mapping):
    
    @abstractmethod
    def __origin_getitem__(self, key: str) -> T: pass
    
    def __getitem__(self, key: str) -> T | None:
        '''
        let mapping['key?'] return mapping.get('key')
        let mapping['key-'] return mapping.pop('key')
        let mapping['key-?'] return mapping.pop('key', None)
        '''
        if key.endswith('?'):
            return self.get(key[:-1])
        return self.__origin_getitem__(key)
    

# ABC class
class NullSafeMutableMapping[T](MutableMapping, NullSafeMapping):  # type: ignore
    @abstractmethod
    def __origin_setitem__(self, key: str, value: T) -> None: pass
    
    @abstractmethod
    def __origin_delitem__(self, key: str) -> None: pass
    
    @abstractmethod
    def __origin_getitem__(self, key: str) -> T: pass
    
    def __getitem__(self, key: str) -> T | None:
        '''
        let mapping['key?'] return mapping.get('key')
        let mapping['-key'] return mapping.pop('key')
        let mapping['-key?'] return mapping.pop('key', None)
        '''
        if key.endswith('?') and not key.startswith('-'):
            return self.get(key[:-1])
        elif not key.endswith('?') and key.startswith('-'):
            return self.pop(key[1:])
        elif key.endswith('?') and key.startswith('-'):
            return self.pop(key[1:-1], None)
        return self.__origin_getitem__(key)
    
    set = __origin_setitem__
    
    def __setitem__(self, key: str, value: T):
        '''
        let mapping['*key?'] = value do:
        ```python
        # I want to update 'key', but I'm not sure if it already exists
        # so I'll qustion it first, so I chose '?'
        # '*?' means 'maybe update?'
        if 'key' in mapping:
            mapping['key'] = value
        ```
        
        let mapping['+key?'] = value do:
        ```python
        # I want to add 'key', but I'm not sure if it already exists
        # So I'll qustion it first, so I chose '?'
        # Because I want to add, not update, so I'll use '+'
        # '+?' means 'maybe add?'
        if not 'key' in mapping:
            mapping['key'] = value
        ```
        
        let mapping['*key!'] = value do:
        ```python
        # I want to update 'key', And I'm VERY SURE it already exists
        # if this key doesn't exist, It will make critical error,
        # so I'll use '!', this will stop the program if the key doesn't exist
        # '*!' means 'must update!'
        if not 'key' in mapping:
            raise KeyError(f"Key {key} not found in dictionary")
        mapping['key'] = value
        ```
        
        let mapping['+key!'] = value do:
        ```python
        # I want to add 'key', And I'm VERY SURE it doesn't exist
        # if this key already exists, It will make critical error,
        # so I'll use '!', this will stop the program if the key already exists
        # Because I want to add, not update, so I'll use '+'
        # '+!' means 'must add!'
        if 'key' in mapping:
            raise KeyError(f"Key {key} already exists in dictionary")
        mapping['key'] = value
        ```
        
        let mapping['key?'] = value do:
        ```python
        if value is not None:
            mapping[key] = value
        ```
        
        let mapping['key!'] = value do:
        ```python
        if value is None:
            raise ValueError(f"Value for key {key} can't be None")
        mapping[key] = value
        ```
        
        summury:
            -- ? will never raise Error, if he found he can't complete the action, it will do nothing.
            -- ! will MUST complete your mission, if he can't complete it, it will raise Error.
            -- * will try to update the key, if failed, do what showed in '!' and '?'
            -- + will try to add the key, if failed, do what showed in '!' and '?'
        
        provied '+' or '*' and not provide '?' or '!'
        '''
        if not isinstance(key, str):
            raise AttributeError("Keys must be strings")
        if key.endswith('?'):
            # nullable mode, if the key already exists, don't set it
            if key[:-1] in self.keys():
                return
            return self.__origin_setitem__(key[:-1], value)
        elif key.endswith('!'):
            # notnull mode, if the key doesn't exist, raise KeyError
            if not key[:-1] in self.keys():
                raise KeyError(f"Key {key[:-1]} not found in dictionary")
            return self.__origin_setitem__(key[:-1], value)
        else:
            return self.__origin_setitem__(key, value)
    
    def __delitem__(self, key: str):
        '''
        let del mapping['key?'] do:
        ```python
        if key in mapping:
            del mapping[key]
        ```
        let del mapping['key!'] do:
        ```python
        if key in mapping:
            del mapping[key]
        else:
            raise KeyError(f"Key {key} not found in dictionary")
        ```
        '''
        if key.endswith('?'):
            if key[:-1] in self.keys():
                return self.__origin_delitem__(key[:-1])
        elif key.endswith('!'):
            if key[:-1] in self.keys():
                return self.__origin_delitem__(key[:-1])
            else:
                raise KeyError(f"Key {key[:-1]} not found in dictionary")
        else:
            return self.__origin_delitem__(key)


def _null_safe_immutable_mapping_cls[T](cls: type[Mapping[str, T]], modify_metadatas: bool = True) -> type[NullSafeMapping[T]]:
    if issubclass(cls, NullSafeMapping):
        return cls
    class _wrapper_cls(cls):  # type: ignore
        __origin_getitem__ = cls.__getitem__
        __getitem__ = NullSafeMapping.__getitem__
    if modify_metadatas:
        update_wrapper(_wrapper_cls, cls)
    return _wrapper_cls


def _null_safe_mutable_mapping_cls[T](cls: type[MutableMapping[str, T]], modify_metadatas: bool = True) -> type[NullSafeMutableMapping[T]]:
    if issubclass(cls, NullSafeMutableMapping):
        return cls
    class _wrapper_cls(cls):  # type: ignore
        __origin_getitem__ = cls.__getitem__
        __getitem__ = NullSafeMutableMapping.__getitem__
        __origin_setitem__ = cls.__setitem__
        __setitem__ = NullSafeMutableMapping.__setitem__
        __origin_delitem__ = cls.__delitem__
        __delitem__ = NullSafeMutableMapping.__delitem__
    if modify_metadatas:
        update_wrapper(_wrapper_cls, cls)
    return _wrapper_cls


def _null_safe_mapping_cls[T](cls: type[Mapping[str, T]]) -> type[NullSafeMapping[T]]:
    if issubclass(cls, MutableMapping):
        return _null_safe_mutable_mapping_cls(cls)
    if issubclass(cls, Mapping):
        return _null_safe_immutable_mapping_cls(cls)
    else:
        raise TypeError("Unsupported mapping type")


def _null_safe_immutable_mapping_instance[T](obj: Mapping[str, T]) -> NullSafeMapping[T]:
    if isinstance(obj, NullSafeMapping):
        return obj
    obj_copy = deepcopy(obj)
    obj_copy.__class__ = _null_safe_mapping_cls(obj.__class__)
    if not isinstance(obj_copy, NullSafeMapping):
        raise TypeError("This error should not happen, use to lie type checker")
    return obj_copy


def _null_safe_mutable_mapping_instance[T](obj: MutableMapping[str, T]) -> NullSafeMutableMapping[T]:
    if isinstance(obj, NullSafeMutableMapping):
        return obj
    obj_copy = deepcopy(obj)
    obj_copy.__class__ = _null_safe_mutable_mapping_cls(obj.__class__)  # error here
    if not isinstance(obj_copy, NullSafeMutableMapping):
        raise TypeError("This error should not happen, use to lie type checker")
    return obj_copy


def _null_safe_mapping_instance[T](obj: Mapping[str, T]) -> NullSafeMapping[T]:
    if isinstance(obj, NullSafeMapping):
        return obj
    if isinstance(obj, MutableMapping):
        return _null_safe_mutable_mapping_instance(obj)
    if isinstance(obj, Mapping):
        return _null_safe_immutable_mapping_instance(obj)
    else:
        raise TypeError("Unsupported mapping type")


def null_safe_mutable_mapping(obj_or_cls: ObjOrCls[MutableMapping[str, Any]]):
    if isinstance(obj_or_cls, type):
        return _null_safe_mapping_cls(obj_or_cls)
    return _null_safe_mutable_mapping_instance(obj_or_cls)


def null_safe_mapping(obj_or_cls: ObjOrCls[Mapping[str, Any]]):
    if isinstance(obj_or_cls, type):
        return _null_safe_mapping_cls(obj_or_cls)
    return _null_safe_mapping_instance(obj_or_cls)




@_null_safe_mutable_mapping_cls
class NullSafeDict[T](dict[str, T], NullSafeMutableMapping[T]):
    pass


# NullSafeDict = _null_safe_mutable_mapping_cls(dict, False)
# NullSafeDefaultDict = _null_safe_mutable_mapping_cls(defaultdict, False)
# NullSafeOrderedDict = _null_safe_mutable_mapping_cls(OrderedDict, False)
# NullSafeChainMap = _null_safe_mutable_mapping_cls(ChainMap, False)
# NullSafeMappingProxyType = null_safe_mapping(MappingProxyType)  # type 'mappingproxy' is not an acceptable base type




# remove this when I make sure this module is no bug.
def test_demo():
    nsd = NullSafeDict({'a': 1, 'b': 2, 'c': 3})
    nsd['a?'] = 2
    nsd['c!'] = 5
    print(nsd['not_exist?'])
    print(nsd)  # run correctly
    dct = {'a': 1, 'b': 2, 'c': 3}
    # nsd = null_safe_mutable_mapping(dct) # AttributeError: 'mappingproxy' object has no attribute 'update'
    # print(nsd)
    
    
if __name__ == '__main__':
    test_demo()