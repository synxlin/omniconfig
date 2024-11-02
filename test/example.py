# -*- coding: utf-8 -*-
"""Test example for omniconfig."""

import argparse
import typing as tp
from dataclasses import dataclass, field

import omniconfig


@omniconfig.configclass
@dataclass
class EvalConfig:
    """Evaluation Config class.

    Attributes:
        num_gpus (int): the number of GPUs. Defaults to ``8``.
    """

    num_gpus: int = 8


@omniconfig.configclass
@dataclass
class QuantConfig:
    """Quantization config class.

    Attributes:
        dtype (str): Quantization data type. Defaults to ``"torch.float16"``.
        group_shape (list[int]): Quantization group shape. Defaults to ``(1, -1)``.
    """

    dtype: str = "torch.float16"
    group_shapes: list[list[int]] = field(
        default=((-1, -1, -1),),
        metadata={omniconfig.ARGPARSE_KWARGS: {"nargs": "+", "type": lambda s: [int(n) for n in s.split(",")]}},
    )


@omniconfig.configclass
@dataclass
class ModelConfig:
    """Model Config class.

    Attributes:
        name (str): the model name.
        group (str): the model family.
    """

    name: str
    family: str = field(init=False, default="")

    def __post_init__(self):
        self.family = self.name.split("-")[0]


@omniconfig.configclass
@dataclass
class QuantizedModelConfig(ModelConfig):
    """Quantized Model Config class.

    Attributes:
        name (str): the model name.
        group (str): the model group.
        quant (QuantConfig): quantization configuration. Defaults to ``None``.
    """

    quant: QuantConfig | None = None


@omniconfig.configclass
@dataclass
class Config:
    """Config class.

    Attributes:
        model (QuantizedModelConfig): the quantized model config.
        eval (EvalConfig): the evaluation config.
    """

    model: QuantizedModelConfig
    eval: EvalConfig

    @classmethod
    def parse_args(
        cls: tp.Self,
        args: tp.Any = None,
    ) -> tuple[
        tp.Self,
        dict[str, tp.Any],
        argparse.Namespace,
        dict[str, dict],
        argparse.Namespace | None,
        list[str],
    ]:
        """Parse arguments.

        Args:
            args (list[str], optional): Arguments to parse. Defaults to ``None``.

        Returns:
            tuple[
                dict[str, Any] | Any,
                dict[str, Any],
                argparse.Namespace,
                dict[str, dict],
                argparse.Namespace | None,
                list[str]
            ]:
                Configs from the parsed arguments, extra arguments,
                unused loaded configs, unused parsed arguments, and unknown arguments.
        """

    @staticmethod
    def dump_default(path: str = "default.yaml") -> None:
        """Dump default configuration to a yaml file.

        Args:
            path (str, optional): The path to save the default configuration. Defaults to ``"default.yaml"``.
        """
        parser = omniconfig.ConfigParser("Evaluate Quantized Model")
        parser.add_config(Config)
        parser.dump_default(path)


@omniconfig.configclass
@dataclass
class ExtraConfig:
    """Extra Config class.

    Attributes:
        test (`bool`, *optional*, default=`False`):
            Test flag.
    """

    test: bool = False


def main(args: tp.Any = None) -> None:  # noqa: C901
    """Evaluate Quantized Model with the given arguments.

    Args:
        args (list[str], optional): Arguments to parse. Defaults to ``None``.
    """
    parser = omniconfig.ConfigParser("Evaluate Quantized Model")
    parser.add_config(Config)
    parser.add_config(ExtraConfig, scope="extra")
    parser.add_extra_argument("--hello", type=int, default=0)
    parser._parser.add_argument("--unused-arg", type=int, default=0)
    configs, extra_args, unused_configs, unused_args, unknown_args = parser.parse_known_args(args)
    assert isinstance(configs[""], Config)
    assert isinstance(configs["extra"], ExtraConfig)
    return configs, extra_args, unused_configs, unused_args, unknown_args


if __name__ == "__main__":
    main()
