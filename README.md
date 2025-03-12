# IFC4.3 Schema Viewer

## Overview

The IFC4.3 Schema Viewer is a NON-OFFICIAL web application built using Streamlit that allows users to visualize and explore the IFC4.3 schema. It provides functionalities for visualizing class and property hierarchies, displaying metadata, and exploring data schema concepts. It is built for study uses.

## Features

- **Class Hierarchy Visualization**: Visualize the inheritance hierarchy of classes in the IFC4.3 schema.
- **Property Hierarchy Visualization**: Visualize the inheritance hierarchy of properties in the IFC4.3 schema.
- **Metadata Display**: Display detailed metadata for selected nodes.
- **Namespace Search**: Search and display namespaces within the IFC4.3 schema.
- **Data Schema Concept Exploration**: Explore various data schema concepts.

## Installation

To install the required dependencies, run the following command:

```bash
pip install -r requirements.txt
```

## Usage

To run the application, execute the following command:

```bash
streamlit run app.py
```

## Project Structure

- `app.py`: The main entry point of the application.
- `ifc_schema_viewer/`: Contains the core application logic and utilities.
  - `apps/`: Contains the application modules.
    - `viewer.py`: Defines the `IfcSchemaViewerApp` class with the main functionalities.
  - `utils/`: Contains utility modules.
    - `echarts.py`: Utility functions for Echarts.
    - `graph_algo.py`: Utility functions for graph algorithms.
- `resources/`: Contains the resources required for the application.
  - `knowledge_graphs/`: Contains the IFC schema graph files.
  - `ontologies/`: Contains ontology files.

## Dependencies

The project requires the following Python packages:

- numpy==2.2.3
- pandas==2.2.3
- pydantic==2.10.6
- rdflib==7.1.3
- streamlit==1.42.0
- streamlit_echarts==0.4.0
- streamlit_extras==0.5.5

## License

This project is licensed under the MIT License. See the LICENSE file for details.
