from dataclasses import dataclass, field
from typing import Any, Callable

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
    group_shape: list[int] = (1, -1)

    @classmethod
    def update_get_arguments(
        cls: type["QuantConfig"],
        *,
        overwrites: dict[str, Callable | None] | None = None,
        defaults: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Callable | None], dict[str, Any]]:
        """Get the arguments for the quantization configuration."""
        overwrites = overwrites or {}
        defaults = defaults or {}
        overwrites.setdefault(
            "group_shape",
            lambda parser: parser.add_argument(
                "--group-shape",
                nargs="+",
                type=int,
                default=defaults.get("group_shape", (1, -1)),
                help="Quantization group shape",
            ),
        )
        return overwrites, defaults


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

    @staticmethod
    def parse_args(args: Any = None) -> tuple["Config", dict[str, dict], list[str]]:
        """Parse arguments.

        Args:
            args (list[str], optional): Arguments to parse. Defaults to ``None``.

        Returns:
            tuple[Config, dict[str, dict], list[str]]: Configs from the parsed arguments,
                                                       parsed yaml configs, and unknown arguments.
        """
        parser = omniconfig.ConfigParser("Evaluate Quantized Model")
        parser.add_config(Config)
        config, parsed_args, unknown_args = parser.parse_known_args(args)
        assert isinstance(config, Config)
        return config, parsed_args, unknown_args

    @staticmethod
    def dump_default(path: str = "default.yaml") -> None:
        """Dump default configuration to a yaml file.

        Args:
            path (str, optional): The path to save the default configuration. Defaults to ``"default.yaml"``.
        """
        parser = omniconfig.ConfigParser("Evaluate Quantized Model")
        parser.add_config(Config)
        parser.dump_default(path)

def main(args: Any = None) -> None:  # noqa: C901
    """Evaluate Quantized Model with the given arguments.

    Args:
        args (list[str], optional): Arguments to parse. Defaults to ``None``.
    """
    config, parsed_args, unknown_args = Config.parse_args(args)


if __name__ == "__main__":
    main()
