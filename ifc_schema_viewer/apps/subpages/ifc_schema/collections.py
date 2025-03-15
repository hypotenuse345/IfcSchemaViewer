import rdflib
from rdflib import RDF, RDFS, OWL
import streamlit as st
from streamlit_echarts import st_echarts
from streamlit_extras.markdownlit import mdlit
from streamlit_extras.stoggle import stoggle
from streamlit_extras.grid import grid as st_grid

from pydantic import BaseModel, PrivateAttr, Field
from typing import List, Optional, Any, Dict, Annotated, Type

from ifc_schema_viewer.utils import EchartsUtility, timer_wrapper

from .individuals import IfcConceptRenderer

ONT = rdflib.Namespace("http://www.semantic.org/zeyupan/ontologies/CoALA4IFC_Schema_Ont#")

class ConceptCollectionInfo(BaseModel):
    _members: Dict[str, Dict[str, Any]] = PrivateAttr(default_factory=dict)
    @property
    def members(self):
        return self._members
    
    _express_types: List[str] = PrivateAttr(default_factory=list)
    @property
    def express_types(self):
        return self._express_types
    
    rdf_graph: Any = Field(default=None, description="RDF graph of IFC Schema")
    
    @property
    def namespace_manager(self):
        return self.rdf_graph.namespace_manager
    
    @timer_wrapper
    def _retrieve_members(self):
        filter_condition = " || ".join([f"?express_type = <{type}>" for type in self.express_types])
        filter_condition = f"FILTER ({filter_condition})"
        query_str = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT DISTINCT ?individual ?individual_name ?express_type
        WHERE {{
            ?individual rdf:type ?express_type ;
                <{ONT["name"]}> ?individual_name.
            {filter_condition}
        }}
        """
        results = self.rdf_graph.query(query_str)
        for result in results:
            self._members[result.individual_name] = {
                "iri": result.individual,
                "name": result.individual_name,
                "express_type": result.express_type.n3(self.namespace_manager)
            }

    def model_post_init(self, __context):
        # Check if the rdf_graph is not None and isinstance of rdflib.Graph
        if not self.rdf_graph or not isinstance(self.rdf_graph, rdflib.Graph):
            raise ValueError("rdf_graph must be an instance of rdflib.Graph")
        self._retrieve_members()
    
    @timer_wrapper
    def render_multiselect(self):
        keyword = st.text_input("输入查询关键词", key=f"collection_info_{self.express_types[0]}")
        if keyword:
            members = {k: v for k, v in self.members.items() if keyword.lower() in k.lower()}
        else:
            members = self.members
        selections = st.multiselect("选择要查看的内容", list(members.keys()))
        return members, selections
    
    @timer_wrapper
    def render(self):
        members, selections = self.render_multiselect()
        if selections:
            if len(selections) > 1:
                grid = st_grid(*[[1,]*2,]*(len(selections) // 2 + len(selections) % 2))
                containers = [grid.container() for i in range(len(selections))]
            else:
                containers = [st.container(),]
            for name, container in zip(selections, containers):
                member = members[name]
                with container:
                    IfcConceptRenderer.display_selected_individual_info(
                        express_type=member["express_type"],
                        individual_iri=member["iri"],
                        ifc_schema_graph=self.rdf_graph
                    )
    
class PSetCollectionInfo(ConceptCollectionInfo):
    def model_post_init(self, __context):
        self._express_types = [ONT["PropertySetTemplate"], ONT["QuantitySetTemplate"]]
        super().model_post_init(__context)

class EntityCollectionInfo(ConceptCollectionInfo):
    def model_post_init(self, __context):
        self._express_types = [ONT["Entity"],]
        super().model_post_init(__context)

class EnumerationCollectionInfo(ConceptCollectionInfo):
    def model_post_init(self, __context):
        self._express_types = [ONT["Enum"],]
        super().model_post_init(__context)

class DerivedTypeCollectionInfo(ConceptCollectionInfo):
    def model_post_init(self, __context):
        self._express_types = [ONT["DerivedType"],]
        super().model_post_init(__context)