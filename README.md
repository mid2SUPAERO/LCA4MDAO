# LCA4MDAO

## Installation

Download from this repository, then install with:
`python setup.py install`

### Dependencies

#### Brightway2 (opensource)

[Brightway2](https://documentation.brightway.dev/en/legacy/index.html) manages the environment databases and LCA calculation. Note that only *Brightway2* is compatible and not *Brightway25*.

#### OpenMDAO (opensource)

[OpenMDAO](https://openmdao.org/newdocs/versions/latest/main.html) manages all the MDAO and optimisation structure.

#### Ecoinvent (licence, optional)

[Ecoinvent](https://ecoinvent.org/) is one of the main environmental database and the one *Brightway2* is built for. Most projects would require a license, which is sadly not free.
Be careful, specific *Ecoinvent* version requires specific *Brightway2* version, as stated on the [documentation](https://github.com/brightway-lca/brightway2-io).

#### Pymoo (opensource, optional)

[Pymoo](https://pymoo.org/) is only required to use the [optimizer](lca4mdao/optimizer) module, mainly for multiobjective optimisation.

## Usage

### Documentation

The notebooks in the [examples](lca4mdao/examples) folder are used as tutorial to understand the usage of the module. Full documentation will be included with the final release.

### Examples

The main principles of the package are highlighted in the simple [sellar notebook](lca4mdao/examples/sellar.ipynb).
The same single objective optimisation problem is condensed in the [sellar](lca4mdao/examples/sellar.py) python file, the multi-objective version in the [sellar_multiobjective](lca4mdao/examples/sellar_multiobjective.py) python file, and a variation using *Ecoinvent 3.8* in the [sellar_ecoinvent](lca4mdao/examples/sellar_ecoinvent.py) python file.

## TODO

- Add to a package registry
- Add precise requirements
- Include utilities for databases other than ecoinvent
- Upgrade to brightway25
- Create other convenient option to generate LCA variables
- Include MDAO parameters inside the normal brightway dependency chain
- Optimise partial derivative computation for LCA
- Include and test more optimiser from pymoo

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## Contact

Author: [Thomas Bellier](mailto:thomas.bellier@isae-supaero.fr)  
PhD supervisor: [Joseph Morlier](mailto:joseph.morlier@isae-supaero.fr)

## Citation

Aerobest conference paper [AerobestPaper](https://hal.science/hal-04188708)

Aerobest slides [AerobestSlides](https://github.com/mid2SUPAERO/LCA4MDAO/blob/master/Aerobest%20LCA4MDAO_JO-compressed.pdf) 

