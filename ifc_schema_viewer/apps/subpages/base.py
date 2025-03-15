import streamlit as st
from streamlit_echarts import st_echarts
from streamlit_extras.grid import grid as st_grid

from typing import List, Dict, Annotated
from pydantic import BaseModel, Field, PrivateAttr, computed_field

from langchain_community.chat_message_histories.streamlit import StreamlitChatMessageHistory

import rdflib
from rdflib import Dataset

class PersonInfo(BaseModel):
    name: str = Field(alias="name")
    email: str = Field(alias="emailAddress")
    last_name: str = Field(alias="familyName")
    first_name: str = Field(alias="givenName")

class SubPage(BaseModel):
    _ifc_schema_dataset: Dataset = PrivateAttr()
    @property
    def ifc_schema_dataset(self):
        return self._ifc_schema_dataset
    
    _classes: List[str] = PrivateAttr(default_factory=list)

    @property
    def classes(self) -> List[str]:
        return self._classes

    _classes_with_individuals: List[str] = PrivateAttr(default_factory=list)

    @property
    def classes_with_individuals(self) -> List[str]:
        return self._classes_with_individuals

    _properties: Dict[str, List[str]] = PrivateAttr(default_factory=dict)
    @property
    def properties(self) -> Dict[str, List[str]]:
        return self._properties

    def model_post_init(self, __context):
        # 建立引用
        self._ifc_schema_dataset = st.session_state.ifc_schema_dataset
        self._classes = st.session_state.classes
        self._properties = st.session_state.properties

    def display_creator_widget(self, container):
        def display_person_info_widget(person_info: PersonInfo):
            return f"""
                <div class="card">
                    <h3>{person_info.name}</h3>
                    <p><i class="fas fa-envelope"></i> <strong>邮箱:</strong> {person_info.email}</p>
                    <p><i class="fas fa-user"></i> <strong>姓:</strong> {person_info.last_name}</p>
                    <p><i class="fas fa-user"></i> <strong>名:</strong> {person_info.first_name}</p>
                </div>
                """
        with container:
            # 自定义CSS
            html_content = """
            <style>
            .card {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                padding: 20px;
                margin: 10px 0;
            }
            .card h3, .card p {
                margin: 0;
                padding: 0;
            }
            .card h3 {
                font-size: 1.5em;
                color: #343a40;
            }
            .card p {
                color: #6c757d;
            }
            </style>
            """
            html_content += '<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css" rel="stylesheet">'
            
            person = PersonInfo(
                name="Zeyu Pan",
                emailAddress="panzeyu@sjtu.edu.cn",
                familyName="Pan",
                givenName="Zeyu",
            )
            html_content += display_person_info_widget(person)
            st.markdown(
                html_content,
                unsafe_allow_html=True,
            )
            
    def _initialize_history(self, history_name="chat_history"):
        """Initialize conversation history for demonstration."""
        return StreamlitChatMessageHistory(history_name)
    
    def render(self):
        raise NotImplementedError()