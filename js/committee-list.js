import orderBy from "lodash/orderBy";
import React from "react";
import LegislatorList, { ChamberButtons } from "./legislator-list";

export default class CommitteeList extends LegislatorList {  

  constructor(props) {
    super(props);
    this.state = {
      ...this.state,
      orderBy: "chamber",
      order: "asc",
    };
  }

  render() {
    const hasUpper = this.props.committees.some(c => c.chamber === "upper");
    const hasLower = this.props.committees.some(c => c.chamber === "lower");
    
    return (
      <div>
        {(hasUpper && hasLower) && (
          <ChamberButtons
            chambers={this.props.chambers}
            chamber={this.state.chamber}
            setChamber={this.setChamber}
          />
        )}
        <table className="hover">
          <thead>
            <tr>
              <th
                onClick={() => this.setSortOrder("name")}
                className="clickable"
              >
                Name
                {this.getSortArrowFor("name")}
              </th>
              <th
                onClick={() => this.setSortOrder("chamber")}
                className="clickable"
              >
                Chamber
                {this.getSortArrowFor("chamber")}
              </th>
              <th
                onClick={() => this.setSortOrder("member_count")}
                className="clickable"
              >
                Members
                {this.getSortArrowFor("member_count")}
              </th>
            </tr>
          </thead>
          <tbody>
            {orderBy(
              this.props.committees,
              [this.state.orderBy, "name"],
              [this.state.orderBy === "chamber" ? (this.state.order === "asc" ? "desc" : "asc") : this.state.order, "asc"]
            )
              .filter(
                committee =>
                  this.state.chamber === null ||
                  committee.chamber === this.state.chamber
              )
              .map(b => (
                <tr key={b.id} className="row--clickable">
                  <td className="u-color--primary">
                    <a href={b.pretty_url} className="row-link">{b.name}</a>
                  </td>
                  <td>{this.props.chambers[b.chamber]}</td>
                  <td>{b.member_count}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    );
  }
}
