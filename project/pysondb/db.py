import collections
import json
import uuid
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import List
from typing import Optional
from typing import Union


try:
    import ujson
    UJSON = True
except ImportError:
    UJSON = False

from pysondb.db_types import DBSchemaType
from pysondb.db_types import IdGeneratorType
from pysondb.db_types import NewKeyValidTypes
from pysondb.db_types import SingleDataType
from pysondb.db_types import ReturnWithIdType
from pysondb.db_types import QueryType
from pysondb.errors import IdDoesNotExistError
from pysondb.errors import SchemaTypeError
from pysondb.errors import UnknownKeyError


# class PysonDB:
#
#     def __init__(self, filename: str, auto_update: bool = True, indent: int = 4) -> None:
#         self.filename = filename
#         self.auto_update = auto_update
#         self._au_memory: DBSchemaType = {'version': 3, 'data': {}}
#         self.indent = indent
#         self._id_generator = self._gen_id
#         self.lock = Lock()
#
#         self._gen_db_file()
#
#     def _load_file(self) -> DBSchemaType:
#         if self.auto_update:
#             with open(self.filename, encoding='utf-8', mode='r') as f:
#                 if UJSON:
#                     return ujson.load(f)
#                 else:
#                     return json.load(f)
#         else:
#             return deepcopy(self._au_memory)
#
#     def _dump_file(self, data: DBSchemaType) -> None:
#         if self.auto_update:
#             with open(self.filename, encoding='utf-8', mode='w') as f:
#                 if UJSON:
#                     ujson.dump(data, f, indent=self.indent)
#                 else:
#                     json.dump(data, f, indent=self.indent)
#         else:
#             self._au_memory = deepcopy(data)
#         return None
#
#     def _gen_db_file(self) -> None:
#         if self.auto_update:
#             if not Path(self.filename).is_file():
#                 self.lock.acquire()
#                 self._dump_file(
#                     {'version': 3, 'data': {}}
#                 )
#                 self.lock.release()
#
#     def _gen_id(self) -> str:
#         # generates a random 18 digit uuid
#         # return str(int(uuid.uuid4()))[:18]
#         return str(uuid.uuid4())
#
#     def force_load(self) -> None:
#         """
#         Used when the data from a file needs to be loaded when auto update is turned off.
#         """
#         if not self.auto_update:
#             self.auto_update = True
#             self._au_memory = self._load_file()
#             self.auto_update = False
#
#     def add(self, data: object) -> str:
#         if not isinstance(data, dict):
#             raise TypeError(f'data must be of type dict and not {type(data)}')
#
#         with self.lock:
#             db_data = self._load_file()
#
#             _id = str(self._id_generator())
#             if not isinstance(db_data['data'], dict):
#                 raise SchemaTypeError(
#                     'data key in the db must be of type "dict"')
#
#             db_data['data'][_id] = data
#             self._dump_file(db_data)
#             return _id
#
#     def add_many(self, data: object, json_response: bool = False) -> Union[SingleDataType, None]:
#
#         if not data:
#             return None
#
#         if not isinstance(data, list):
#             raise TypeError(
#                 f'data must be of type "list" and not {type(data)}')
#
#         if not all(isinstance(i, dict) for i in data):
#             raise TypeError(
#                 'all the new data in the data list must of type dict')
#
#         with self.lock:
#             new_data: SingleDataType = {}
#             db_data = self._load_file()
#
#             if not isinstance(db_data['data'], dict):
#                 raise SchemaTypeError(
#                     'data key in the db must be of type "dict"')
#
#             for d in data:
#                 _id = str(self._id_generator())
#                 db_data['data'][_id] = d
#                 if json_response:
#                     new_data[_id] = d
#             self._dump_file(db_data)
#
#         return new_data if json_response else None
#
#     def get_all(self) -> ReturnWithIdType:
#         with self.lock:
#             data = self._load_file()['data']
#             if isinstance(data, dict):
#                 return data
#         return {}
#
#     def get_by_id(self, id: str) -> SingleDataType:
#         if not isinstance(id, str):
#             raise TypeError(
#                 f'id must be of type "str" and not {type(id)}')
#
#         with self.lock:
#             data = self._load_file()['data']
#             if isinstance(data, dict):
#                 if id in data:
#                     return data[id]
#                 else:
#                     raise IdDoesNotExistError(
#                         f'{id!r} does not exists in the DB')
#             else:
#                 raise SchemaTypeError(
#                     '"data" key in the DB must be of type dict')
#
#     def get_by_query(self, query: QueryType) -> ReturnWithIdType:
#         if not callable(query):
#             raise TypeError(
#                 f'"query" must be a callable and not {type(query)!r}')
#
#         with self.lock:
#             new_data: ReturnWithIdType = {}
#             data = self._load_file()['data']
#             if isinstance(data, dict):
#                 for id, values in data.items():
#                     if isinstance(values, dict):
#                         if query(values):
#                             yield id, values
#
#     def update_by_id(self, id: str, new_data: object) -> SingleDataType:
#         if not isinstance(new_data, dict):
#             raise TypeError(
#                 f'new_data must be of type dict and not {type(new_data)!r}')
#
#         with self.lock:
#             data = self._load_file()
#
#             if id not in data['data']:
#                 raise IdDoesNotExistError(
#                     f'The id {id!r} does noe exists in the DB')
#
#             data['data'][id] = {**data['data'][id], **new_data}
#
#             self._dump_file(data)
#             return data['data'][id]
#
#     def update_by_query(self, query: QueryType, new_data: object) -> List[str]:
#         if not callable(query):
#             raise TypeError(
#                 f'"query" must be a callable and not {type(query)!r}')
#
#         if not isinstance(new_data, dict):
#             raise TypeError(
#                 f'"new_data" must be of type dict and not f{type(new_data)!r}')
#
#         with self.lock:
#             updated_keys = []
#             db_data = self._load_file()
#
#             if not isinstance(db_data['data'], dict):
#                 raise SchemaTypeError(
#                     'The data key in the DB must be of type dict')
#
#             for key, value in db_data['data'].items():
#                 if query(value):
#                     db_data['data'][key] = {**db_data['data'][key], **new_data}
#                     updated_keys.append(key)
#
#             self._dump_file(db_data)
#             return updated_keys
#
#     def delete_by_id(self, id: str) -> None:
#         with self.lock:
#             data = self._load_file()
#             if not isinstance(data['data'], dict):
#                 raise SchemaTypeError(
#                     '"data" key in the DB must be of type dict')
#             if id not in data['data']:
#                 raise IdDoesNotExistError(f'ID {id} does not exists in the DB')
#             del data['data'][id]
#
#             self._dump_file(data)
#
#     def delete_by_query(self, query: QueryType) -> List[str]:
#         if not callable(query):
#             raise TypeError(
#                 f'"query" must be a callable and not {type(query)!r}')
#
#         with self.lock:
#             data = self._load_file()
#             if not isinstance(data['data'], dict):
#                 raise SchemaTypeError(
#                     '"data" key in the DB must be of type dict')
#             ids_to_delete = []
#             for id, value in data['data'].items():
#                 if query(value):
#                     ids_to_delete.append(id)
#             for id in ids_to_delete:
#                 del data['data'][id]
#
#             self._dump_file(data)
#             return ids_to_delete
#
#     def purge(self) -> None:
#         with self.lock:
#             data = self._load_file()
#             if not isinstance(data['data'], dict):
#                 raise SchemaTypeError(
#                     '"data" key in the DB must be of type dict')
#             data['data'] = {}
#             self._dump_file(data)


class PysonDB(collections.UserDict):

    def __init__(self, filename: Path, auto_update: bool = True, indent: int = 4) -> None:
        super().__init__()

        self.filename = filename
        self.auto_update = auto_update
        self._au_memory: DBSchemaType = {'version': 3, 'data': {}}
        self.indent = indent
        self._document_id_generator = PysonDB._generate_document_id
        self.lock = Lock()

        self._generate_empty_database()

    @staticmethod
    def _generate_document_id() -> str:
        # generates a random 18 digit uuid
        # return str(int(uuid.uuid4()))[:18]
        return str(uuid.uuid4())

    def _load_database(self) -> DBSchemaType:
        if self.auto_update:
            with open(self.filename, encoding='utf-8', mode='r') as f:
                data = ujson.load(f) if UJSON else json.load(f)

                if isinstance(data, dict):
                    raise SchemaTypeError(
                        'Loaded data must of type dict')

                if isinstance(data['data'], dict):
                    raise SchemaTypeError(
                        '"data" key in the DB must be of type dict')

                return data

        else:
            return deepcopy(self._au_memory)

    def _save_database(self, data: DBSchemaType) -> None:
        if self.auto_update:
            with open(self.filename, encoding='utf-8', mode='w') as f:
                if UJSON:
                    ujson.dump(data, f, indent=self.indent)
                else:
                    json.dump(data, f, indent=self.indent)
        else:
            self._au_memory = deepcopy(data)

        return None

    def _generate_empty_database(self) -> None:
        if self.auto_update:
            if not Path(self.filename).is_file():
                self.lock.acquire()
                self._save_database(
                    {'version': 3, 'data': {}}
                )
                self.lock.release()

    def commit(self) -> None:
        if not self.auto_update:
            self.auto_update = True
            self._save_database(self._au_memory)
            self.auto_update = False

    def set_id_generator(self, fn: IdGeneratorType) -> None:
        self._document_id_generator = fn

    def add(self, data: object) -> str:
        if not isinstance(data, dict):
            raise TypeError(f'data must be of type dict and not {type(data)}')

        with self.lock:
            db_data = self._load_database()

            _id = str(self._document_id_generator())
            if not isinstance(db_data['data'], dict):
                raise SchemaTypeError(
                    'data key in the db must be of type "dict"')

            db_data['data'][_id] = data
            self._save_database(db_data)
            return _id

    def add_many(self, data: object, json_response: bool = False) -> Union[SingleDataType, None]:

        if not data:
            return None

        if not isinstance(data, list):
            raise TypeError(
                f'data must be of type "list" and not {type(data)}')

        if not all(isinstance(i, dict) for i in data):
            raise TypeError(
                'all the new data in the data list must of type dict')

        with self.lock:
            new_data: SingleDataType = {}
            db_data = self._load_database()

            if not isinstance(db_data['data'], dict):
                raise SchemaTypeError(
                    'data key in the db must be of type "dict"')

            for d in data:
                _id = str(self._document_id_generator())
                db_data['data'][_id] = d
                if json_response:
                    new_data[_id] = d
            self._save_database(db_data)

        return new_data if json_response else None

    def __getitem__(self, document_id: str) -> SingleDataType:
        if not isinstance(document_id, str):
            raise TypeError(
                f'id must be of type "str" and not {type(document_id)}')

        with self.lock:
            data = self._load_database()['data']
            if document_id not in data:
                raise IdDoesNotExistError(
                    f'{document_id!r} does not exists in the DB')

            return data[document_id]

    def __setitem__(self, key, val):
        raise NotImplementedError()

    def get_by_query(self, query: QueryType) -> ReturnWithIdType:
        if not callable(query):
            raise TypeError(
                f'"query" must be a callable and not {type(query)!r}')

        with self.lock:
            new_data: ReturnWithIdType = {}
            data = self._load_database()['data']
            if isinstance(data, dict):
                for id, values in data.items():
                    if isinstance(values, dict):
                        if query(values):
                            new_data[id] = values

            return new_data

    def update_by_id(self, document_id: str, new_data: object) -> SingleDataType:
        if not isinstance(new_data, dict):
            raise TypeError(
                f'new_data must be of type dict and not {type(new_data)!r}')

        with self.lock:
            data = self._load_database()

            if document_id not in data['data']:
                raise IdDoesNotExistError(
                    f'The id {document_id!r} does noe exists in the DB')

            data['data'][document_id] = {**data['data'][document_id], **new_data}

            self._save_database(data)
            return data['data'][document_id]

    def update_by_query(self, query: QueryType, new_data: object) -> List[str]:
        if not callable(query):
            raise TypeError(
                f'"query" must be a callable and not {type(query)!r}')

        if not isinstance(new_data, dict):
            raise TypeError(
                f'"new_data" must be of type dict and not f{type(new_data)!r}')

        with self.lock:
            updated_keys = []
            db_data = self._load_database()

            if not isinstance(db_data['data'], dict):
                raise SchemaTypeError(
                    'The data key in the DB must be of type dict')

            for key, value in db_data['data'].items():
                if query(value):
                    db_data['data'][key] = {**db_data['data'][key], **new_data}
                    updated_keys.append(key)

            self._save_database(db_data)
            return updated_keys

    def __delitem__(self, document_id: str) -> None:
        with self.lock:
            data = self._load_database()
            if not isinstance(data['data'], dict):
                raise SchemaTypeError(
                    '"data" key in the DB must be of type dict')
            if document_id not in data['data']:
                raise IdDoesNotExistError(f'ID {document_id} does not exists in the DB')
            del data['data'][document_id]

            self._save_database(data)

    def delete_by_query(self, query: QueryType) -> List[str]:
        if not callable(query):
            raise TypeError(
                f'"query" must be a callable and not {type(query)!r}')

        with self.lock:
            data = self._load_database()
            if not isinstance(data['data'], dict):
                raise SchemaTypeError(
                    '"data" key in the DB must be of type dict')
            ids_to_delete = []
            for document_id, value in data['data'].items():
                if query(value):
                    ids_to_delete.append(document_id)
            for document_id in ids_to_delete:
                del data['data'][document_id]

            self._save_database(data)
            return ids_to_delete

    def purge(self) -> None:
        with self.lock:
            data = self._load_database()
            data['data'] = {}
            self._save_database(data)

    def __len__(self):
        with self.lock:
            data = self._load_database()
            return len(data)

    def __iter__(self):
        with self.lock:
            data = self._load_database()
            return iter(data)

    # Modify __contains__ and get() to work like dict
    # does when __missing__ is present.
    def __contains__(self, key):
        with self.lock:
            data = self._load_database()
            return key in data

    def get(self, key, default=None):
        if key in self:
            return self[key]
        return default

