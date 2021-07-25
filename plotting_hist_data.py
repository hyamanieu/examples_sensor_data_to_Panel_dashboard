#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import panel as pn
import pandas as pd
import hvplot.pandas
import holoviews as hv
from sqlalchemy import create_engine
import param
from bokeh.models.formatters import DatetimeTickFormatter


# In[ ]:


from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, schema
from sqlalchemy.orm import sessionmaker
import os


# In[ ]:


import datetime as dt


# In[ ]:


XFORMATTER = DatetimeTickFormatter()
XFORMATTER.years = ['%Y-%m-%d']
XFORMATTER.months = ['%Y-%m-%d']
XFORMATTER.days = ['%d/%m']


# In[ ]:


pn.extension()


# In[ ]:


POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD= os.getenv('POSTGRES_PASSWORD')
POSTGRES_ADDRESS= os.getenv('POSTGRES_ADDRESS')


# In[ ]:


engine = create_engine('postgresql://{0}:{1}@{2}/sensors'.format(POSTGRES_USER,
                                                                              POSTGRES_PASSWORD,
                                                                              POSTGRES_ADDRESS))


# In[ ]:


Session = sessionmaker(bind=engine)
session = Session()
Base = declarative_base()
Base.metadata.reflect(engine,schema='th')


# In[ ]:





# In[ ]:


Base.metadata.tables.keys()


# In[ ]:


tablename = 'th.bureau'
table = Base.metadata.tables[tablename]
dates = (table.c.msg_ts <= dt.date.today()) & (table.c.msg_ts >= dt.date.today()-dt.timedelta(days=3))
query = session.query(table).filter(dates)


# In[ ]:


session.rollback()


# In[ ]:


class Historic_Data_Panel(param.Parameterized):
    
    source = param.Selector(default='check_one_room', objects=['check_one_room','compare_rooms'])
    lower_date = param.Date(default=dt.date.today()-dt.timedelta(days=3),bounds=(None,dt.date.today()))
    upper_date = param.Date(default=dt.date.today(),bounds=(None,dt.date.today()))
    
    plot_kind = param.Selector(default='line',objects=['line','scatter'])
    t_list = list(Base.metadata.tables.keys())
    table_selector = param.ListSelector(default=t_list[:1], objects=t_list)
    y_selec = param.Selector(default='temperature',objects=['temperature','humidity','pressure',
                                                            'linkquality','battery','voltage'])
    
    table_selector2 = param.Selector(default=t_list[0], objects=t_list)
    y_selec2 = param.ListSelector(default=['temperature','humidity','pressure'],
                                 objects=['temperature','humidity','pressure',
                                                            'linkquality','battery','voltage'])
    
    @param.depends('upper_date','lower_date',watch=True)
    def load_dataframes(self):
        self.dfs = {}
        self.show_stuff.object = "{0} => {1}".format(self.lower_date,self.upper_date)
        for tablename, table in Base.metadata.tables.items():
            dates = ((table.c.msg_ts <= self.upper_date+dt.timedelta(days=1)) 
                     & (table.c.msg_ts >= self.lower_date))
            query = session.query(table).filter(dates)
            self.dfs[tablename] = pd.DataFrame(query.all())
            
            
            
    @param.depends('table_selector','y_selec','upper_date','lower_date','plot_kind')
    def show_plot(self):
        l=[]
        grid_style = {"grid_line_color":"olive",
                      "minor_grid_line_color":None}
        for tn in self.table_selector:
            p = self.dfs[tn].hvplot(kind=self.plot_kind,x='msg_ts',y=self.y_selec,rot=20,xformatter=XFORMATTER,
                                        label=tn,responsive=True).opts(show_grid=True)
            l.append(p)
            
        
        o = hv.Overlay(l)
        
        return pn.pane.HoloViews(o,sizing_mode="stretch_both",min_width=600,min_height=800)
    
    @param.depends('table_selector2','y_selec2','upper_date','lower_date','plot_kind')
    def show_plot2(self):
        tn = self.table_selector2
        l=[]
        grid_style = {"grid_line_color":"olive",
                     "minor_grid_line_color":None}
        def_opt = dict(gridstyle=grid_style,
                   show_grid=True)
        for i, y in enumerate(self.y_selec2):
            p = self.dfs[tn].hvplot(kind=self.plot_kind,x='msg_ts',y=y,rot=20,xformatter=XFORMATTER,responsive=True,
                                        min_height=150,min_width=300)
            if i==0:
                p.opts(xaxis='top',**def_opt)
            else:
                p.opts(xaxis=None, **def_opt)
            l.append(p)
        o = hv.Layout(l).cols(1)
        return pn.pane.HoloViews(o,sizing_mode="stretch_both",min_width=600,min_height=800)
    
    @param.depends('source')
    def body(self):
        if self.source != "check_one_room":
            return self.show_plot
        else:
            return self.show_plot2
    @param.depends('source')   
    def widgets(self):
        if self.source != "check_one_room":
            return pn.Param(self.param,name=self.source.replace('_',' '),
                     parameters=['table_selector','y_selec'],
                     height_policy='fit',
                     width_policy='fit')
        else:             
            return pn.Param(self.param,name=self.source.replace('_',' '),
                     parameters=['table_selector2','y_selec2'],
                     height_policy='fit',
                     width_policy='fit')
        
    
    def __init__(self,**params):
        super().__init__(**params)
        self.show_stuff = pn.pane.markup.Markdown(object='')
        self.load_dataframes()
        
        



# In[ ]:


mypanel = Historic_Data_Panel()


# In[ ]:


bootstrap = pn.template.BootstrapTemplate(title='Bootstrap Template')


bootstrap.sidebar.extend([
    pn.Param(mypanel.param,
             widgets={'source': pn.widgets.Select,
                      'lower_date':pn.widgets.DatePicker,
                      'upper_date':pn.widgets.DatePicker},
             parameters=['source','lower_date','upper_date','plot_kind'],
             height_policy='fit',
             width_policy='fit',
             name='Sensors'),
    mypanel.widgets       
        
    ]
)

bootstrap.main.append(mypanel.body)
         


# In[ ]:


bootstrap.servable()


# In[ ]:




