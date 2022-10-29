import os, sys
from abc import ABCMeta, abstractmethod
from logging import Logger
from typing import (
    Any, Callable, Optional, TypeVar, Union, 
    Literal, Sequence, List
)
from ..core.make import MakeSummary

from .group_mixins.memo import MemoMixin
from .group_mixins.selector import SelectorMixin

from ..rule.memo.abc import IMemo
from ..rule.memo.pickle_memo import PickleMemo
from ..rule.memo.str_hash_memo import StrHashMemo
from .. import logwriter
from .group_common import IGroup, GroupTreeInfo, make

StrOrPath = Union[str, os.PathLike[Any]]

TMemoKind = Literal["str_hash", "pickle"]

T = TypeVar("T")

class GroupBase(SelectorMixin, MemoMixin, IGroup, metaclass=ABCMeta):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def namefq(self) -> str:
        ...

    # mixin methods
    def __init__(
        self,
        dirname: Optional[StrOrPath] = None,
        prefix: Optional[StrOrPath] = None,
        *,
        loglevel: Optional[logwriter.Loglevel] = None,
        use_default_logger: bool = True,
        logfile: Union[
            None, StrOrPath, Logger, logwriter.WritableProtocol,
            Sequence[Union[StrOrPath, Logger, logwriter.WritableProtocol]],
        ] = None,
        memo_kind: TMemoKind = "str_hash",
        pickle_key: Union[None, str, bytes] = None,
    ):
        writer = _staticgroup__init__parse_logwriter(
            loglevel, use_default_logger, logfile
        )

        memo_factory = \
            _staticgroup__init__args_memo_factory(memo_kind, pickle_key)

        info = GroupTreeInfo(writer, memo_factory)

        self.__init_as_child__(info, self, ())

        self.set_prefix(_staticgroup__init__parse_prefix(dirname, prefix))


    def clean(self) -> None:
        raise NotImplementedError()

    def touch(self) -> None:
        raise NotImplementedError()

    def make(
        self,
        dry_run: bool = False,
        keep_going: bool = False,
        *,
        njobs: Optional[int] = None,
    ) -> MakeSummary:
        """Make rules in this group and their dependencies

        Args:
            dry_run (bool):
                instead of actually excuting the methods,
                print expected execution logs.
            keep_going (bool):
                If False (default), stop everything when a rule fails.
                If True, when a rule fails, keep executing other rules
                except the ones depend on the failed rule.
            njobs (int):
                Maximum number of rules that can be made concurrently.
                Defaults to 1 (single process, single thread).

        See also:
            See the description of jtcmake.make for more detail of njobs
        """
        return make(
            self,
            dry_run=dry_run,
            keep_going=keep_going,
            njobs=njobs,
        )



def _staticgroup__init__parse_logwriter(
    loglevel: object, use_default_logger: object, logfile: object
) -> logwriter.IWriter:
    if not logwriter.typeguard_loglevel(loglevel):
        raise TypeError(f"loglevel must be {logwriter.Loglevel}. Given {loglevel}")

    if not (isinstance(use_default_logger, bool) or use_default_logger is None):
        raise TypeError(
            f"use_default_logger must be bool or None. "
            f"Given {use_default_logger}"
        )

    logfile_: Sequence[object] = \
        logfile if isinstance(logfile, Sequence) else [logfile]

    writers: List[logwriter.IWriter] = \
        [_create_logwriter(f, loglevel) for f in logfile_]

    if use_default_logger:
        writers.append(create_default_logwriter(loglevel))

    return logwriter.WritersWrapper(writers)


def _create_logwriter(f: object, loglevel: logwriter.Loglevel) -> logwriter.IWriter:
    if isinstance(f, (str, os.PathLike)):
        fname = str(f)
        if fname[-5:] == ".html":
            return logwriter.HTMLFileWriterOpenOnDemand(loglevel, fname)
        else:
            return logwriter.TextFileWriterOpenOnDemand(loglevel, fname)

    if isinstance(f, Logger):
        return logwriter.LoggerWriter(f)

    if isinstance(f, logwriter.WritableProtocol):
        _isatty = getattr(f, "isatty", None)
        if callable(_isatty) and _isatty():
            return logwriter.ColorTextWriter(f, loglevel)

        return logwriter.TextWriter(f, loglevel)

    raise TypeError(
        "Logging target must be either str (file name), os.PathLike, "
        "logging.Logger, or and object with `write` method. "
        f"Given {f}"
    )


def create_default_logwriter(loglevel: logwriter.Loglevel) -> logwriter.IWriter:
    if logwriter.term_is_jupyter():
        return logwriter.HTMLJupyterWriter(loglevel, os.getcwd())
    elif sys.stderr.isatty():
        return logwriter.ColorTextWriter(sys.stderr, loglevel)
    else:
        return logwriter.TextWriter(sys.stderr, loglevel)

def _staticgroup__init__args_memo_factory(
    kind: object, pickle_key: object
) -> Callable[[object], IMemo]:
    if kind == "str_hash":
        if pickle_key is not None:
            raise TypeError(
                "pickle_key must not be specified for "
                "str_hash memoization"
            )
        return StrHashMemo
    elif kind == "pickle":
        if pickle_key is None:
            raise TypeError("pickle_key must be specified")
        
        if isinstance(pickle_key, str):
            try:
                pickle_key_ = bytes.fromhex(pickle_key)
            except ValueError as e:
                raise ValueError(
                    "If given as str, pickle_key must be a hexadecimal string"
                ) from e
        elif isinstance(pickle_key, bytes):
            pickle_key_ = pickle_key
        else:
            raise TypeError("pickle_key must be bytes or hexadecimal str")

        def _memo_factory_pickle(args: object) -> IMemo:
            return PickleMemo(args, pickle_key_)

        return _memo_factory_pickle
    else:
        raise TypeError("memo kind must be \"str_hash\" or \"pickle\"")


def _staticgroup__init__parse_prefix(dirname: object, prefix: object) -> str:
    if dirname is not None and prefix is not None:
        raise TypeError(
            "Either dirname or prefix, but not both must be specified"
        )

    if dirname is not None:
        if not isinstance(dirname, (str, os.PathLike)):
            raise TypeError("dirname must be str or PathLike")

        prefix_ = str(dirname) + os.path.sep
    else:
        if prefix is None:
            prefix_ = ""
        elif isinstance(prefix, (str, os.PathLike)):
            prefix_ = str(prefix)
        else:
            raise TypeError("prefix must be str or PathLike")

    return prefix_
