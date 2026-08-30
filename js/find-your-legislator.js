import React from "react";
import ReactDOM from "react-dom";
import stateBounds from "./state-bounds";
import LegislatorImage from "./legislator-image";
import config from "./config";


export default class FindYourLegislator extends React.Component {
  constructor(props) {
    super(props);
    const queryParams = new URLSearchParams(window.location.search);

    // extract state from path if state is not US
    const pathParts = window.location.pathname.split('/').filter(part => part);
    const stateAbbr = pathParts.length > 0 && pathParts[0] !== 'us' 
      ? pathParts[0] 
      : ""; 
        
    this.state = {
      address: props.address || "",
      lat: queryParams.get("lat") || 0,
      lon: queryParams.get("lon") || 0,
      geocodedAddress: null,
      relevance: null,
      stateAbbr: stateAbbr,
      legislators: [],
      stateLegislators:[],
      federalLegislators:[],
      error: "",
    };

    this.handleAddressChange = this.handleAddressChange.bind(this);
    this.handleDrag = this.handleDrag.bind(this);
    this.geocode = this.geocode.bind(this);
    this.geolocate = this.geolocate.bind(this);

    if (this.state.lat && this.state.lon) {
      this.updateLegislators();
    } else if (this.state.address) {
      // if we just got an address, geocode
      this.geocode();
    } else if (queryParams.get("geolocate")) {
      this.geolocate();
    }
  }

  handleAddressChange(event) {
    this.setState({ address: event.target.value });
  }

  handleDrag(event) {
    this.setState({
      lat: event.lngLat.lat,
      lon: event.lngLat.lng,
    });
    this.updateLegislators();
  }

  setError(message) {
    this.setState({
      error: message,
      legislators: [],
      geocodedAddress: null,
      relevance: null,
    });
  }

  geolocate() {
    const component = this;
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        function(position) {
          component.setState({
            lat: position.coords.latitude,
            lon: position.coords.longitude,
          });
          component.updateLegislators();
        },
        function() {
          component.setError(
            "Geolocation was not available, try entering your address."
          );
        }
      );
    } else {
      component.setError(
        "Geolocation was not available, try entering your address."
      );
    }
  }

  geocode() {
    const component = this;

    // if stateAbbr, limit geocoding to bounding box
    const bb = this.state.stateAbbr ? stateBounds[this.state.stateAbbr] : null;
    const bbStr = this.state.stateAbbr
      ? `&bbox=${bb[0][0]},${bb[0][1]},${bb[1][0]},${bb[1][1]}`
      : "";
    const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encodeURI(
      this.state.address
    )}.json?country=US&limit=1${bbStr}&access_token=${
      config.MAPBOX_ACCESS_TOKEN
    }`;

    // set error message depending on whether accessing from specific state (stateAbbr)
    const geocoding_error_message = component.state.stateAbbr
      ? "Unable to geolocate your address, try adding more information. We are not currently able to locate legislators for addresses outside " + component.state.stateAbbr.toUpperCase() + " but hope to add support for this in the future."
      : "Unable to geolocate your address, try adding more information.";

    fetch(url)
      .then(response => response.json())
      .then(function(json) {

        // return error message if relevance is not returned (e.g. if mapbox cannot geocode search term)
        if (!json.features || json.features.length === 0) {
          component.setError(geocoding_error_message);
          return;
        }

        // return error message if relevance (geocoding accuracy) is below threshold
        const relevance = json.features[0].relevance
        const RELEVANCE_THRESHOLD = 0.7;
        
        if (relevance < RELEVANCE_THRESHOLD) {
          component.setError(geocoding_error_message);
          return;
        }

        // if stateAbbr, return error message if geocoded state is different than inital state 
        // (this can happen even when limiting geocoding to state bounding box because state bounds are not exact)
        if (component.state.stateAbbr) {
          const context = json.features[0].context;
          let stateContext = null;
          let geocodedState = null;

          if (context) {
            stateContext = context.find(function(c) {
              return c.id.startsWith('region');
            });
          }

          if (stateContext && stateContext.short_code) {
            geocodedState = stateContext.short_code.replace('US-', '').toLowerCase();
            if (geocodedState !== component.state.stateAbbr) {
              component.setError(geocoding_error_message);
              return;
            }
          }
        }

        component.setState({
          lat: json.features[0].center[1],
          lon: json.features[0].center[0],
          geocodedAddress: json.features[0].place_name,  
          relevance: json.features[0].relevance,
        });
        component.updateLegislators();
      })
      .catch(function(error) {
        console.error(error);
        component.setError(geocoding_error_message);
      });
  }

  updateLegislators() {
    if (!this.state.lat || !this.state.lon) {
      this.setState({ legislators: [], stateLegislators:[], federalLegislators:[] });
    } else {
      const component = this;
      const statePrefix = this.state.stateAbbr ? this.state.stateAbbr : 'us';
      const llUrl = `/${statePrefix}/find_your_legislator/?lat=${this.state.lat}&lon=${this.state.lon}&address=${this.state.address}`;
      fetch(llUrl + "&json=json")
        .then(response => response.json())
        .then(function(json) {
          component.setState({ legislators: json.legislators, error: null });
          component.splitLegislators();
        });
    }
  }

  splitLegislators() {
    let stateLegislators = [];
    let federalLegislators = [];
    this.state.legislators.map(leg => {
      const level = leg.level;
      if (level === 'state')
        return stateLegislators.push(leg);
      federalLegislators.push(leg);
    });
    this.setState({ stateLegislators, federalLegislators });
  }

  renderLegislators(legislators) {
    // sort in reverse alphabetical order by chamber (upper first)
    legislators.sort((a, b) => b.chamber.localeCompare(a.chamber)); 

    const rows = legislators.map(leg => (
      <tr key={leg.name}>
        <td>
          <LegislatorImage id={leg.id} image={leg.image} party={leg.party} />
        </td>
        <td>
          <a href={leg.pretty_url}>{leg.name}</a>
        </td>
        <td>{leg.party}</td>
        <td>{leg.district}</td>
        <td>{leg.chamber.charAt(0).toUpperCase() + leg.chamber.slice(1)}</td>
      </tr>
    ));
    let table;

    if (this.state.legislators.length) {
      // have to wrap this in a div or the grid sizing will explode the table
      table = (
        <div>
          <h3>State</h3>
          <table id="results">
            <thead>
              <tr>
                <th className="show-for-sr">Image</th>
                <th>Name</th>
                <th>Party</th>
                <th>District</th>
                <th>Chamber</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
      );
    }
    const federalTable = this.renderFederalLegislator(this.state.federalLegislators);

    const section = (
      <div>
        {table}{federalTable}
      </div>
    );

    return section;
  }

    renderFederalLegislator(legislators) {
      const rows = legislators.map(leg => {
        const office = leg.chamber == 'upper' ? 'U.S. Senate': `U.S. House ${leg.district}`;
        return (
        <tr key={leg.name}>
          <td>
            <LegislatorImage id={leg.id} image={leg.image} party={leg.party} />
          </td>
          <td>
            <a href={leg.pretty_url}>{leg.name}</a>
          </td>
          <td>{leg.party}</td>
          <td>{office}</td>
        </tr>
      )});
      let table;

      if (this.state.legislators.length) {
        table = (
          <div>
            <h3>Federal</h3>
            <table id="results">
              <thead>
                <tr>
                  <th className="show-for-sr">Image</th>
                  <th>Name</th>
                  <th>Party</th>
                  <th>Office</th>
                </tr>
              </thead>
              <tbody>{rows}</tbody>
            </table>
          </div>
        );
      }

    return table;
  }


  render() {
    const legTables = this.renderLegislators(this.state.stateLegislators);
    const stateAbbrForPlaceholder = this.state.stateAbbr ? this.state.stateAbbr.toUpperCase() : 'CT';
    return (
      <div className="find-your-legislator">
        <div>
          <h2 className="heading--small mb1">
             Find out who represents you by entering your address below:
          </h2>
          <div className="input-group">
            <input
              className="input-group-field"
              type="search"
              id="fyl-address"
              name="address"
              placeholder={`Ex: 111 River Road, Storrs, ${stateAbbrForPlaceholder} 12345`}
              value={this.state.address}
              onChange={this.handleAddressChange}
            />
            <div className="input-group-button">
              <button
                id="address-lookup"
                className="button button--primary"
                onClick={this.geocode}
              >
                Search by Address
              </button>
            </div>
          </div>

          <div className="mapbox-credit">
              In most cases, this should be your pre-incarceration address. Learn more <a href="/resources/">here</a>.
          </div>

          {this.state.error ? ( 
            // if error message 
            <div className="mapbox-credit">
              <div className="fyl-error">{this.state.error}</div>
            </div>
          ) : ( 
            // if geocoding successful
            this.state.geocodedAddress ? ( 
              <div className="mapbox-credit">
                <strong>Located Address:</strong> {this.state.geocodedAddress}
                {this.state.relevance < 1.0 && " (Partial match)"}
              </div>
            ) : null
          )}

          <div className="mapbox-credit">
              Post-redistricting geographic data graciously provided by Redistricting Data Hub.
          </div>
          
          <div className="mapbox-credit">Geolocation powered by <img
              src="/static/images/logos/mapbox-logo-black.png" alt="Mapbox" />.
          </div>

        </div>
        
        <div>
          
          {legTables}

        </div>
      </div>
    );
  }
}

window.addEventListener("load", () => {
  const fyl = document.querySelector('[data-hook="find-your-legislator"]');
  ReactDOM.render(
    React.createElement(FindYourLegislator, {
      address: fyl.getAttribute("data-address"),
    }), fyl
  );
});
