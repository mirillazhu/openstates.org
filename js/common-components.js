import React from "react";
import ReactDOM from "react-dom";
import LegislatorImage from "./legislator-image";
import LegislatorList from "./legislator-list";
import CommitteeList from "./committee-list";
import FollowButton from "./follow-button";

window.addEventListener("load", () => {
  const ll = document.querySelector('[data-hook="legislator-list"]');
  if (ll) {
    ReactDOM.render(
      React.createElement(LegislatorList, {
        legislators: window.legislators,
        chambers: window.chambers,
      }),
      ll
    );
  }

  const cl = document.querySelector('[data-hook="committee-list"]');
  if (cl) {
    ReactDOM.render(
      React.createElement(CommitteeList, {
        committees: window.committees,
        chambers: window.chambers,
      }),
      cl
    );
  }

  const images = document.querySelectorAll('[data-hook="legislator-image"]');
  for (var img of images) {
    ReactDOM.render(
      React.createElement(LegislatorImage, {
        image: img.getAttribute("data-image"),
        id: img.getAttribute("data-person-id"),
        size: img.getAttribute("data-size"),
        party: img.getAttribute("data-party"),
      }),
      img
    );
  }

  const buttons = document.querySelectorAll('[data-hook="follow-button"]');
  for (var fb of buttons) {
    ReactDOM.render(
      React.createElement(FollowButton, {
        billId: fb.getAttribute("data-bill-id"),
        latestActionId: fb.getAttribute("data-latest-action-id"),
        isFollowing: fb.getAttribute("data-following"),
      }),
      fb
    );
  }
});
