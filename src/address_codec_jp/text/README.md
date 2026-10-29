# text

## Overview

Address text processing that needs no database of its own: text is normalized, matched
to a registered town, and rendered back from an `Address`.

## Components

| Component | Responsibility |
| --- | --- |
| [normalization/](normalization/) | Text normalization, kanji numerals, and lot number parsing |
| [matching/](matching/) | Longest-prefix matching from normalized text to a registered town |
| [formatting/](formatting/) | Output format options and address rendering |
