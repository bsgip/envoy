from abc import ABC
from typing import Dict


class BaseMapper(ABC):
    _map = {}

    @classmethod
    def _map_colnames(cls, input_dict: Dict):
        res_dict = {}
        for k, v in input_dict.items():
            if k in cls._map:
                res_dict[cls._map[k]] = v
        return res_dict
