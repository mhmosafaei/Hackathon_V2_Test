import React, {useEffect, useRef, useState} from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

export function validPosition(value) {
  return Array.isArray(value) && value.length === 2 && value.every(v=>typeof v==='number' && Number.isFinite(v)) && Math.abs(value[0])<=90 && Math.abs(value[1])<=180;
}
export function validGeometry(geometry) {
  if (!geometry || !['Polygon','MultiPolygon'].includes(geometry.type)) return null;
  const polygons=geometry.type==='Polygon' ? [geometry.coordinates] : geometry.coordinates;
  if (!Array.isArray(polygons) || !polygons.length) return null;
  const valid=polygons.every(polygon=>Array.isArray(polygon) && polygon.length && polygon.every(ring=>Array.isArray(ring) && ring.length>=4 && ring.every(p=>Array.isArray(p) && p.length===2 && validPosition([p[1],p[0]])) && ring[0][0]===ring.at(-1)[0] && ring[0][1]===ring.at(-1)[1]));
  return valid ? geometry : null;
}
const tooltip = text => {const element=document.createElement('span');element.textContent=text;return element;};

export default function EnvironmentalMapCanvas({position, sample, geometry, valueLabel, focusToken}) {
  const container=useRef(null), map=useRef(null), layers=useRef(null), boundsKey=useRef('');
  const [tileError,setTileError]=useState(false);
  useEffect(()=>{
    const instance=L.map(container.current,{scrollWheelZoom:false,zoomControl:true}).setView([25,0],2);
    map.current=instance;
    L.control.scale({position:'bottomright',metric:true,imperial:false,maxWidth:100}).addTo(instance);
    const tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(instance);
    tiles.on('tileerror',()=>setTileError(true));
    tiles.on('tileload',()=>setTileError(false));
    layers.current=L.featureGroup().addTo(instance);
    const observer=typeof ResizeObserver!=='undefined' ? new ResizeObserver(()=>instance.invalidateSize()) : null;
    observer?.observe(container.current);
    return ()=>{observer?.disconnect();instance.remove();map.current=null;layers.current=null;};
  },[]);
  useEffect(()=>{
    if (!map.current || !layers.current) return;
    const group=layers.current;group.clearLayers();
    const shape=validGeometry(geometry);
    if (shape) L.geoJSON(shape,{style:{color:'#147e8a',weight:2,fillColor:'#27acb5',fillOpacity:.14}}).bindTooltip(tooltip('Work area boundary · evidence remains specific to sampled locations')).addTo(group);
    if (validPosition(position)) L.circleMarker(position,{radius:9,color:'#fff',weight:3,fillColor:'#147e8a',fillOpacity:1}).bindTooltip(tooltip('Confirmed work location')).addTo(group);
    if (validPosition(sample)) L.circleMarker(sample,{radius:6,color:'#b97721',weight:2,fillColor:'#ffcc7a',fillOpacity:1}).bindTooltip(tooltip(valueLabel),{permanent:true,direction:'top',offset:[0,-8],className:'environment-map-tooltip'}).addTo(group);
    const key=JSON.stringify([position,sample,shape,focusToken]);
    if (boundsKey.current!==key && group.getLayers().length) {
      map.current.invalidateSize();
      map.current.fitBounds(group.getBounds(),{padding:[55,65],maxZoom:11,animate:false});
      boundsKey.current=key;
    }
  },[position?.[0],position?.[1],sample?.[0],sample?.[1],geometry,valueLabel,focusToken]);
  return <><div ref={container} className="environment-leaflet-map" aria-label="Environmental evidence map" role="region"/>{tileError && <p className="environment-map-tile-error" role="status">Basemap tiles could not be loaded. Location markers and evidence details remain available.</p>}</>;
}
