import { useMemo, useState } from "react";

import { practiceEvents, practicePlaces, TOMSK_CENTER } from "../../infrastructure/mockPracticeMap.js";
import { BottomNav } from "../BottomNav.jsx";
import { Toast } from "../Toast.jsx";
import { Topbar } from "../Topbar.jsx";
import { useApp } from "../AppContext.jsx";

const MAP_ZOOM = 13;
const MAP_WIDTH = 390;
const MAP_HEIGHT = 420;
const TILE_SIZE = 256;

export function PracticeMap() {
  const { showToast, toast } = useApp();
  const [mode, setMode] = useState("map");
  const [selectedPlaceId, setSelectedPlaceId] = useState(practicePlaces[0]?.id);
  const selectedPlace = practicePlaces.find((place) => place.id === selectedPlaceId) ?? practicePlaces[0];
  const tiles = useMemo(() => buildTiles(TOMSK_CENTER, MAP_ZOOM), []);

  return (
    <>
      <div className="shell">
        <Topbar onToast={showToast} />
        <main className="practice-page" aria-labelledby="practice-map-title">
          <section className="page-hero compact practice-hero">
            <span className="eyebrow">Карта</span>
            <h1 id="practice-map-title">Практика рядом</h1>
            <p>Точки в Томске для практики навыков из маршрутов и список ближайших тематических мероприятий.</p>
          </section>

          <div className="map-switcher" role="tablist" aria-label="Режим карты">
            <button className={mode === "map" ? "active" : ""} type="button" role="tab" aria-selected={mode === "map"} onClick={() => setMode("map")}>
              Карта
            </button>
            <button className={mode === "events" ? "active" : ""} type="button" role="tab" aria-selected={mode === "events"} onClick={() => setMode("events")}>
              Мероприятия
            </button>
          </div>

          {mode === "map" ? (
            <MapMode tiles={tiles} selectedPlace={selectedPlace} onSelectPlace={setSelectedPlaceId} />
          ) : (
            <EventsMode />
          )}
        </main>
      </div>
      <BottomNav />
      <Toast message={toast} />
    </>
  );
}

function MapMode({ tiles, selectedPlace, onSelectPlace }) {
  return (
    <>
      <section className="practice-map-card" aria-label="OpenStreetMap, Томск">
        <div className="practice-map" role="img" aria-label="Тёмная карта OpenStreetMap с точками практики в Томске">
          <div className="tile-layer" aria-hidden="true">
            {tiles.map((tile) => (
              <img
                key={`${tile.x}-${tile.y}`}
                alt=""
                className="map-tile"
                src={`https://a.basemaps.cartocdn.com/dark_all/${MAP_ZOOM}/${tile.x}/${tile.y}.png`}
                style={{
                  height: `${(TILE_SIZE / MAP_HEIGHT) * 100}%`,
                  left: `${(tile.left / MAP_WIDTH) * 100}%`,
                  top: `${(tile.top / MAP_HEIGHT) * 100}%`,
                  width: `${(TILE_SIZE / MAP_WIDTH) * 100}%`,
                }}
              />
            ))}
          </div>
          <div className="map-vignette" aria-hidden="true" />
          <span className="map-city-label">{TOMSK_CENTER.label}</span>
          {practicePlaces.map((place) => {
            const point = projectPoint(place, TOMSK_CENTER, MAP_ZOOM);
            const isSelected = place.id === selectedPlace.id;
            return (
              <button
                key={place.id}
                className={`practice-pin ${isSelected ? "active" : ""}`}
                type="button"
                style={{ left: `${point.left}%`, top: `${point.top}%` }}
                aria-label={place.title}
                onClick={() => onSelectPlace(place.id)}
              >
                <span className="pin-core" aria-hidden="true" />
              </button>
            );
          })}
          <div className="map-attribution">© OpenStreetMap · CARTO Dark</div>
        </div>
      </section>

      <PlaceDetails place={selectedPlace} />
    </>
  );
}

function PlaceDetails({ place }) {
  return (
    <section className="place-details" aria-labelledby="selected-place-title">
      <div className="place-head">
        <div>
          <span>{place.category}</span>
          <h2 id="selected-place-title">{place.title}</h2>
        </div>
        <strong>+ {place.reward}</strong>
      </div>
      <p>{place.description}</p>
      <div className="place-meta">
        <span>{place.track}</span>
        <span>{place.format}</span>
        <span>{place.schedule}</span>
      </div>
      <small>{place.address}</small>
    </section>
  );
}

function EventsMode() {
  return (
    <section className="events-list" aria-label="Мероприятия по маршрутам">
      {practiceEvents.map((event) => (
        <article key={event.id} className="event-card">
          <div className="event-date">
            <strong>{event.date}</strong>
            <span>{event.time}</span>
          </div>
          <div className="event-body">
            <div className="event-head">
              <span>{event.topic}</span>
              <b>+ {event.reward}</b>
            </div>
            <h2>{event.title}</h2>
            <p>{event.description}</p>
            <div className="place-meta">
              <span>{event.place}</span>
              <span>{event.level}</span>
            </div>
          </div>
        </article>
      ))}
    </section>
  );
}

function buildTiles(center, zoom) {
  const centerPoint = projectWorld(center.lat, center.lng, zoom);
  const startX = Math.floor((centerPoint.x - MAP_WIDTH / 2) / TILE_SIZE);
  const endX = Math.floor((centerPoint.x + MAP_WIDTH / 2) / TILE_SIZE);
  const startY = Math.floor((centerPoint.y - MAP_HEIGHT / 2) / TILE_SIZE);
  const endY = Math.floor((centerPoint.y + MAP_HEIGHT / 2) / TILE_SIZE);
  const tiles = [];

  for (let x = startX; x <= endX; x += 1) {
    for (let y = startY; y <= endY; y += 1) {
      tiles.push({
        x,
        y,
        left: x * TILE_SIZE - centerPoint.x + MAP_WIDTH / 2,
        top: y * TILE_SIZE - centerPoint.y + MAP_HEIGHT / 2,
      });
    }
  }

  return tiles;
}

function projectPoint(place, center, zoom) {
  const centerPoint = projectWorld(center.lat, center.lng, zoom);
  const placePoint = projectWorld(place.lat, place.lng, zoom);
  return {
    left: ((placePoint.x - centerPoint.x + MAP_WIDTH / 2) / MAP_WIDTH) * 100,
    top: ((placePoint.y - centerPoint.y + MAP_HEIGHT / 2) / MAP_HEIGHT) * 100,
  };
}

function projectWorld(lat, lng, zoom) {
  const sinLat = Math.sin((lat * Math.PI) / 180);
  const scale = TILE_SIZE * 2 ** zoom;
  return {
    x: ((lng + 180) / 360) * scale,
    y: (0.5 - Math.log((1 + sinLat) / (1 - sinLat)) / (4 * Math.PI)) * scale,
  };
}
