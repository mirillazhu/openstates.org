import React from "react";
import Cookies from "js-cookie";

export default class FollowButton extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      following: JSON.parse(this.props.isFollowing.toLowerCase()),
    };
    this.toggle = this.toggle.bind(this);
  }

  toggle() {
    const csrftoken = Cookies.get("csrftoken");
    var method;
    if (this.state.following) {
      this.setState({ following: false });
      method = "DELETE";
    } else {
      this.setState({ following: true });
      method = "POST";
    }

    fetch("/bill_subscription/", {
      method: method,
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": csrftoken,
      },
      body: JSON.stringify({ 
        bill_id: this.props.billId, 
        latest_action_id: this.props.latestActionId 
      }),
    })
      .then(response => {
        return response.json();
      })
      .then(json => {
        this.setState({ following: json.active });
      });
  }

  render() {
    if (this.state.following) {
      return (
        <a className="button" id="followButton" onClick={this.toggle}>
          Unfollow Bill
        </a>
      );
    } else {
      return (
        <a className="button" id="followButton" onClick={this.toggle}>
          Follow Bill
        </a>
      );
    }
  }
}
