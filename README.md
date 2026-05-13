# Westwide fuel treatment effects analysis
<!-- Logos -->
<table width="100%">
    <tr>
        <td align="left">
            <a href="https://reshapewildfire.org/"><img src="https://reshapewildfire.org/assets/reshape-logo-color.svg" alt="ReSHAPE" width="200"/>
            <rect width="100%" height="100%" fill="#ffffff"/></a>
        </td>
        <td align="right">
            <a href="https://sweri.org/"><img src="https://reshapewildfire.org/assets/sweri-logo.svg" alt="SWERI" width="120"/>
            <rect width="100%" height="100%" fill="#ffffff"/></a>
        </td>
    </tr>
</table>
Authors: the ReSHAPE Biophysical Effects team  
- Anson Call [a.call@colostate.edu](mailto:a.call@colostate.edu)  
- Nathan Tomczyk [ntomczyk@nmhu.edu](mailto:ntomczyk@nmhu.edu)  
- and many others!

Short description
-----------------
Analysis and reproducible workflows to estimate fuel treatment effects across the western U.S. using TWIG fuel treatment data. Includes data download, processing, analysis, and figure/report generation.

<!-- centered + sized using HTML heading -->
<h3 align="center"><strong>This is a work in progress!</strong></h3>
<h3 align="center"><strong>Expected completion: Q1 2027</strong></h3>

Badges
------
[![](https://img.shields.io/badge/license-GNU_GPLv3-green)]()

Table of contents
-----------------
- [Setup](#setup)
- [Data](#data)
- [Project structure](#project-structure)
- [Usage](#usage)
- [Reproducibility](#reproducibility)
- [Cite](#cite)

Setup
-----
Requirements

- R >= 4.0 (tidyverse, sf, terra, renv) 
- Stan (rstan)
- Python >= 3.8 (numpy)
- ArcGIS (ArcPy)

Data
-----
Raw data is streamed directly from the TWIG database and other sources. Run the pull_data.R script to download raw data. Expect 10-20 gigabytes. 

Project structure
-----------------
```
.  
├── README.md  
├── .gitignore  
├── renv.lock  
├── data/  
│   ├── raw/            # fill with raw data using pull_data.R  
│   └── tidy/           # analysis-ready derived data outputs  
├── src/                # main analysis code in here
│   ├── data_prep/  
│   │   ├── pull_data.R
│   │   └── prepare_data.R  
│   ├── analysis/  
│   │   ├── burn_severity.R
│   │   ├── fire_spread.R
│   │   └── resilience.R  
│   ├── models/  
│   │   ├── burn_severity_model.stan  
│   │   ├── fire_spread_model.stan  
│   │   └── resilience_model.stan  
│   ├── utilities/  
│   │   ├── plot_helpers.R  
│   │   └── raster_helpers.R  
│   └── run_pipeline.R  
├── figures/            # generated; ignored by git  
└── tests/              # ancillary analysis
    ├── conditional_independence.R  
    └── test_data_prep.R  
```

Usage
-----
To replicate the published analysis in its entirety, open the project in your IDE (RStudio, Positron) and run the `run_pipeline.R` script in the `src/` directory. To inspect and validate the analysis, we recommend sourcing the `pull_data.R` script to download the necessary data files.  Then, run  `prepare_data.R` to parse and wrangle the data. Finally, run the scripts in `analysis/` in interactive sessions to explore the results. Additional scripts in the `tests/` directory can be used to validate key statistical assumptions.

Reproducibility
---------------
Reproducibility is an essential aspect of scientific research. This project aims to provide a fully reproducible analysis. If you encounter any issues or have questions about reproducing the analysis, please contact the authors.

Cite
----
To cite this analysis, please cite the associated paper (forthcoming). To cite TWIG data, please cite the following *Data Descriptor* paper:  

Call A, Tomczyk N, Withnall KA, Dappen PR, Heusinkveld D, Mueller S, Holloway B, Shennan K, Herring J, Franko A, Colavito MM, Kimple AD, Meador AS, Stevens-Rumann CS (2025) A new geodatabase of fuel treatments across federal lands in the USA. Scientific Data 12(1), 1485. [https://doi.org/10.1038/s41597-025-05859-z](https://doi.org/10.1038/s41597-025-05859-z)
