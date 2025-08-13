# OmniConfig

A powerful Python library for managing configurations from multiple sources - command-line arguments, configuration files (YAML/JSON), and dataclass defaults - with seamless integration and type safety.

## Features

✨ **Unified Configuration Management**: Seamlessly integrate command-line arguments, YAML/JSON files, and dataclass defaults  
🔗 **Cross-Configuration References**: Reference values between different configuration sections using `::path::to::value`  
🎯 **Type Safety**: Full type hint support with automatic type validation and conversion  
📝 **Decorator-Based**: Simple `@dataclass` decorator approach - no complex class hierarchies  
🔄 **Smart Merging**: Intelligent merging of configurations from multiple sources with clear precedence  
🏭 **Custom Type Support**: Register custom types with factory and reducer functions  
📂 **Hierarchical Defaults**: Automatic discovery and loading of `__default__.yaml` files  
🎨 **Flexible CLI Generation**: Automatic generation of command-line arguments from dataclass fields  

## Installation

### From PyPI

```bash
pip install omniconfig
```

### From Source

```bash
git clone https://github.com/synxlin/omniconfig
cd omniconfig
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/synxlin/omniconfig
cd omniconfig
uv sync  # or: pip install -e ".[dev]"
```

## Quick Start

```python
from dataclasses import dataclass, field
from typing import List
from omniconfig import OmniConfigParser

@dataclass
class ModelConfig:
    layers: List[int] = field(default_factory=lambda: [128, 64, 32])
    dropout: float = 0.1

@dataclass
class TrainingConfig:
    learning_rate: float = 0.001
    batch_size: int = 32
    epochs: int = 100
    model: ModelConfig = field(default_factory=ModelConfig)

# Create parser and register configs
parser = OmniConfigParser()
parser.add_config(TrainingConfig, scope="train")

# Parse from command line
# python train.py --train-learning-rate=0.01 --train-model-layers 256 128 64
config, *_ = parser.parse_known_args()

# Access configuration
print(config.train.learning_rate)   # 0.01
print(config.train.model.layers)    # [256, 128, 64]
```

## Core Concepts

### Dataclass Configurations

OmniConfig works with standard Python dataclasses:

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    username: str = "admin"
    password: Optional[str] = None
    options: Dict[str, str] = field(default_factory=dict)
```

### Scopes and Flags

- **Scope**: Namespace where config is stored (`config.train`, `config.model`)
- **Flag**: CLI prefix for arguments (`--train-lr`, `--model-size`)

```python
parser = OmniConfigParser()

# Default: scope and flag are the same
parser.add_config(TrainingConfig, scope="train")
# CLI: --train-learning-rate 0.001

# Custom flag
parser.add_config(ModelConfig, scope="model", flag="m")  
# CLI: --m-layers 128 64

# Empty flag (no prefix)
parser.add_config(DataConfig, scope="data", flag="")
# CLI: --path /data/train
```

## Usage Examples

### Basic Configuration

```python
from dataclasses import dataclass
from omniconfig import OmniConfigParser

@dataclass
class AppConfig:
    app_name: str = "MyApp"
    debug: bool = False
    port: int = 8080
    host: str = "0.0.0.0"

parser = OmniConfigParser()
parser.add_config(AppConfig, scope="app")

# Parse command line: python app.py --app-debug=true --app-port=9000
config, *_ = parser.parse_known_args()

print(f"Starting {config.app.app_name} on {config.app.host}:{config.app.port}")
```

### Nested Configurations

```python
@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432

@dataclass
class CacheConfig:
    enabled: bool = True
    ttl: int = 3600

@dataclass
class ServerConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    workers: int = 4

parser = OmniConfigParser()
parser.add_config(ServerConfig, scope="server")

# CLI: --server-database-host db.example.com --server-cache-ttl 7200
config, *_ = parser.parse_known_args()
```

### Configuration Files

Create a YAML configuration file `config.yaml`:

```yaml
train:
  learning_rate: 0.001
  batch_size: 64
  optimizer:
    name: adam
    momentum: 0.9
    weight_decay: 0.0001

model:
  architecture: resnet50
  layers: [64, 128, 256, 512]
  dropout: 0.2
```

Load it with OmniConfig:

```python
@dataclass
class OptimizerConfig:
    name: str = "sgd"
    momentum: float = 0.9
    weight_decay: float = 0.0

@dataclass
class TrainConfig:
    learning_rate: float = 0.01
    batch_size: int = 32
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)

@dataclass
class ModelConfig:
    architecture: str = "resnet18"
    layers: List[int] = field(default_factory=lambda: [64, 128])
    dropout: float = 0.1

parser = OmniConfigParser()
parser.add_config(TrainConfig, scope="train")
parser.add_config(ModelConfig, scope="model")

# Load from file and override with CLI
# python train.py config.yaml --train-batch-size 128
config, *_ = parser.parse_known_args()
```

### Cross-Configuration References

Reference values from other configurations using the `::scope::field` syntax:

```yaml
# shared_config.yaml
shared:
  learning_rate: 0.001
  optimizers:
    adam:
      beta1: 0.9
      beta2: 0.999
    sgd:
      momentum: 0.9
      nesterov: true

train:
  # Reference shared learning rate
  learning_rate: "::shared::learning_rate"
  # Reference and override specific fields
  optimizer:
    _reference_: "::shared::optimizers::adam"
    beta1: 0.95  # Override beta1

eval:
  # Direct reference (no overrides)
  optimizer: "::shared::optimizers::adam"
```

```python
@dataclass
class OptimizerConfig:
    beta1: float = 0.9
    beta2: float = 0.999

@dataclass  
class SharedConfig:
    learning_rate: float = 0.001
    optimizers: Dict[str, OptimizerConfig] = field(default_factory=dict)

@dataclass
class TrainConfig:
    learning_rate: float = 0.01
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)

parser = OmniConfigParser()
parser.add_config(SharedConfig, scope="shared")
parser.add_config(TrainConfig, scope="train")

config, *_ = parser.parse_known_args(["shared_config.yaml"])

# train.learning_rate references shared.learning_rate
assert config.train.learning_rate == config.shared.learning_rate

# train.optimizer is a modified copy of shared.optimizers.adam
assert config.train.optimizer.beta1 == 0.95  # Overridden
assert config.train.optimizer.beta2 == 0.999  # From reference
```

### Custom Types

Register custom types for automatic conversion:

```python
from pathlib import Path
from datetime import datetime
from omniconfig import OmniConfig

# Register Path type
OmniConfig.register_type(
    Path,
    type_hint=str,
    factory=lambda x: Path(x),
    reducer=lambda x: str(x)
)

# Register datetime type
OmniConfig.register_type(
    datetime,
    type_hint=str,
    factory=lambda x: datetime.fromisoformat(x),
    reducer=lambda x: x.isoformat()
)

@dataclass
class ExperimentConfig:
    name: str = "experiment"
    output_dir: Path = Path("./outputs")
    checkpoint_dir: Optional[Path] = None
    start_time: datetime = field(default_factory=datetime.now)
    model_paths: List[Path] = field(default_factory=list)

parser = OmniConfigParser()
parser.add_config(ExperimentConfig, scope="exp")

# CLI: --exp-output-dir /data/outputs --exp-model-paths model1.pt model2.pt
config, *_ = parser.parse_known_args()

assert isinstance(config.exp.output_dir, Path)
assert isinstance(config.exp.start_time, datetime)
```

### Complex Data Structures

```python
from typing import Dict, List, Optional, Union

@dataclass
class DatasetConfig:
    name: str
    path: str
    batch_size: int = 32
    shuffle: bool = True

@dataclass
class ExperimentConfig:
    # Dict of datasets
    datasets: Dict[str, DatasetConfig] = field(default_factory=dict)
    
    # List of metric names
    metrics: List[str] = field(default_factory=lambda: ["accuracy", "loss"])
    
    # Nested dict structure
    hyperparameters: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Union types
    scheduler: Optional[Union[str, Dict[str, float]]] = None

parser = OmniConfigParser()
parser.add_config(ExperimentConfig, scope="exp")

# From YAML
yaml_config = """
exp:
  datasets:
    train:
      name: imagenet_train
      path: /data/imagenet/train
      batch_size: 256
    val:
      name: imagenet_val
      path: /data/imagenet/val
      shuffle: false
  
  metrics: [accuracy, top5_accuracy, loss]
  
  hyperparameters:
    optimizer:
      lr: 0.001
      momentum: 0.9
    scheduler:
      gamma: 0.1
      step_size: 30
"""

# Or from CLI with JSON syntax
# --exp-datasets '{"train": {"name": "custom", "path": "/data"}}'
# --exp-hyperparameters optimizer.lr=0.01 scheduler.gamma=0.2
```

## Advanced Features

### Priority and Merging

Configuration sources have the following priority (highest to lowest):
1. Command-line arguments
2. Explicitly specified configuration files
3. Default configuration files (`__default__.yaml`)
4. Dataclass defaults

```python
# dataclass default: 0.001
# default.yaml: 0.01  
# config.yaml: 0.02
# CLI: --train-learning-rate 0.03

# Final value: 0.03 (CLI wins)
```

### Hierarchical Default Files

OmniConfig automatically discovers and loads `__default__.yaml` files:

```
configs/
├── __default__.yaml          # Global defaults
└── experiments/
    ├── __default__.yaml      # Experiment defaults
    └── resnet/
        ├── __default__.yaml  # ResNet defaults
        └── resnet50.yaml     # Specific config
```

### Partial Updates vs Overwrites

```python
# Partial update (merge)
--train-optimizer lr=0.001 momentum=0.9

# Complete overwrite
--train-optimizer '{"lr": 0.001, "momentum": 0.9}'

# In YAML
train:
  optimizer:
    _overwrite_: true  # Replace entire optimizer
    lr: 0.001
    momentum: 0.9
```

### List and Dict Operations

```python
@dataclass
class Config:
    layers: List[int] = field(default_factory=lambda: [128, 64])
    params: Dict[str, float] = field(default_factory=dict)

# List overwrite
--config-layers 256 128 64

# List partial update (by index)
--config-layers 0=256 2=32

# Dict operations
--config-params lr=0.001 momentum=0.9
--config-params '{"lr": 0.001, "momentum": 0.9}'  # Overwrite
```

### Extra Arguments

Handle additional arguments not part of configs:

```python
parser = OmniConfigParser()
parser.add_config(TrainConfig, scope="train")
parser.add_extra_argument("--wandb-project", type=str)
parser.add_extra_argument("--seed", type=int, default=42)

config, extra_args, *_ = parser.parse_known_args()

print(extra_args.wandb_project)  # Access extra arguments
print(extra_args.seed)           # 42 (default)
```

## API Reference

### OmniConfigParser

```python
parser = OmniConfigParser(
    prog=None,                        # Program name
    description=None,                 # Program description  
    parser=None,                      # Use existing ArgumentParser
    suppress_cli=False,               # Disable CLI argument generation
    keep_cli_flag_underscores=False,  # Keep underscores in flags
)
```

**Methods:**
- `add_config(cls, scope="", flag=None, help="")`: Register a dataclass configuration
- `add_extra_argument(*args, **kwargs)`: Add additional argument (same as ArgumentParser)
- `parse_known_args(args=None)`: Parse arguments and return configuration
- `set_logging_level(level)`: Set logging verbosity

**Returns from `parse_known_args()`:**
```python
config, extra_args, unused_args, used_data, unused_data, unknown_args = parser.parse_known_args()
```
- `config`: OmniConfigNamespace with all configurations
- `extra_args`: Namespace with extra CLI arguments
- `unused_args`: Namespace with unused CLI arguments
- `used_data`: Dict of used config fields
- `unused_data`: Dict of unused config fields
- `unknown_args`: List of unknown CLI arguments

### OmniConfig

Global registry for custom types:

```python
# Register a custom type
OmniConfig.register_type(
    type_,       # The custom type class
    type_hint,   # Type hint for parsing (e.g., str, dict[str, float])
    factory,     # Function to create type from type_hint
    reducer      # Function to convert type to type_hint
)

# Check if type is registered
OmniConfig.is_type_registered(Path)  # True/False

# Clear all registered types
OmniConfig.clear_type_registry()
```

### OmniConfigNamespace

Container for parsed configurations:

```python
# Access by attribute
config.train.learning_rate

# Access by key
config["train"]["learning_rate"]

# Get configuration object
train_config = config.train  # Returns TrainingConfig instance
```

## Configuration File Formats

### YAML Format

```yaml
# Basic fields
train:
  learning_rate: 0.001
  batch_size: 32
  epochs: 100

# Nested configs
model:
  encoder:
    layers: [128, 256, 512]
    dropout: 0.1
  decoder:
    layers: [512, 256, 128]
    dropout: 0.2

# References
experiment:
  model: "::model::encoder"
  optimizer:
    _reference_: "::shared::optimizers::adam"
    lr: 0.01  # Override

# Lists and dicts
data:
  datasets:
    - name: train
      path: /data/train
    - name: val
      path: /data/val
  augmentations:
    flip: true
    rotate: 90
```

### JSON Format

```json
{
  "train": {
    "learning_rate": 0.001,
    "batch_size": 32,
    "epochs": 100
  },
  "model": {
    "layers": [128, 256, 512],
    "dropout": 0.1
  },
  "references": {
    "_reference_": "::shared::base_config",
    "custom_field": "override"
  }
}
```

## Error Handling

### Common Errors

```python
# Type mismatch
ConfigParseError: Cannot parse 'abc' as int for field 'batch_size'

# Missing required field  
ConfigValidationError: Missing required field 'name' in DataConfig

# Invalid reference
ConfigReferenceError: Cannot resolve reference '::invalid::path'

# Circular reference
CircularReferenceError: Circular reference detected: a → b → c → a
```

## Best Practices

1. **Use Type Hints**: Always provide type hints for better validation and IDE support
2. **Provide Defaults**: Set sensible defaults for all fields when possible
3. **Organize with Scopes**: Group related configurations under logical scopes
4. **Document Fields**: Use docstrings to document configuration classes
5. **Validate Early**: Validate configurations as soon as they're loaded
6. **Use References**: Avoid duplication by using references for shared values
7. **Version Configs**: Keep configuration files in version control

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/synxlin/omniconfig
cd omniconfig

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=omniconfig

# Format code
ruff format .

# Lint code
ruff check .
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by OmegaConf, and argparse
- Designed for researchers and developers who need flexible configuration management
