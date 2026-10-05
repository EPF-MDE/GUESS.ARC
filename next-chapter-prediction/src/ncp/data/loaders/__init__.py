"""Chargeurs de dataset.

Un chargeur est une fonction `(path, config) -> Iterator[RawRecord]`. Il ne
connait rien du pipeline : il lit un format et rend des dictionnaires. Pour
brancher un format maison, ecrire la fonction et l'enregistrer :

    from ncp.data.loaders import register_loader

    @register_loader("mon_format", extensions=(".mon",))
    def load_mon_format(path, config):
        yield {"chapter": 1, "summary": "..."}
"""

from ncp.data.loaders.base import (
    LoaderError,
    available_loaders,
    detect_format,
    get_loader,
    iter_raw_records,
    register_loader,
)

# Les modules ci-dessous s'enregistrent a l'import : les garder importes ici.
from ncp.data.loaders import markdown as _markdown  # noqa: F401
from ncp.data.loaders import tabular as _tabular  # noqa: F401
from ncp.data.loaders import text as _text  # noqa: F401

__all__ = [
    "LoaderError",
    "available_loaders",
    "detect_format",
    "get_loader",
    "iter_raw_records",
    "register_loader",
]
