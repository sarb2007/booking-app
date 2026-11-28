// login function
async function login() {
    const res = await fetch("/login", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
        }),
    });
    const status = document.getElementById("status");
    if (!res.ok) {
        status.textContent = "Invalid email or password";
        return;
    }
    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    status.textContent = "Logged in";
    loadBookings();
}


// load services function
async function loadServices() {
    const res = await fetch("/services");
    const services = await res.json();
    const list = document.getElementById("services");
    for (const s of services) {
        const li = document.createElement("li");
        li.textContent = `${s.name} - ${s.duration_min} min - £${s.price}`;
        list.appendChild(li);
        const option = document.createElement("option");
        option.value = s.id;
        option.textContent = s.name;
        document.getElementById("service-select").appendChild(option);
    }
}
loadServices();


// load slots function



async function loadSlots() {
  const id = document.getElementById("service-select").value;
  const date = document.getElementById("date").value;
  const msg = document.getElementById("slots-msg");
  const list = document.getElementById("slots");
  list.replaceChildren();
  if (!id || !date) {
    msg.textContent = "Choose a service and a date";
    return;
  }
  msg.textContent = "";
  const res = await fetch(`/services/${id}/slots?date=${date}`);
  const slots = await res.json();
  if (slots.length === 0) {
    msg.textContent = "No slots on this day";
    return;
  }
  for (const s of slots) {
    const li = document.createElement("li");
    li.textContent = s.start_time.slice(11) + (s.available ? " - free" : " - taken");
    li.className = s.available ? "free" : "taken";
    if (s.available) {
    const btn = document.createElement("button");
    btn.textContent = "Book";
    btn.onclick = () => bookSlot(id, s.start_time);
    li.appendChild(btn);
    }
    list.appendChild(li);
  }
}

// book slot function

async function bookSlot(serviceId, startTime) {
  const token = localStorage.getItem("token");
  const msg = document.getElementById("book-msg");
  if (!token) {
    msg.textContent = "Please log in first";
    return;
  }
  const res = await fetch("/bookings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token,
    },
    body: JSON.stringify({service_id: Number(serviceId), start_time: startTime}),
  });
  if (res.status === 201) {
    msg.textContent = "Booked! Check your email.";
  } else if (res.status === 409) {
    msg.textContent = "Sorry, that slot was just taken";
  } else if (res.status === 401 || res.status === 403) {
    msg.textContent = "Please log in as a customer";
  } else {
    msg.textContent = "Something went wrong";
  }
  loadSlots();
  loadBookings();
}

// load bookings function

async function loadBookings() {
  const token = localStorage.getItem("token");
  const msg = document.getElementById("bookings-msg");
  const list = document.getElementById("bookings");
  list.replaceChildren();
  if (!token) {
    msg.textContent = "Log in to see your bookings";
    return;
  }
  const res = await fetch("/bookings", {
    headers: {"Authorization": "Bearer " + token},
  });
  if (!res.ok) {
    msg.textContent = "Please log in again";
    return;
  }
  const bookings = await res.json();
  msg.textContent = bookings.length === 0 ? "No bookings yet" : "";
  for (const b of bookings) {
    const li = document.createElement("li");
    li.textContent = `${b.customer ? b.customer + " - " : ""}${b.service} - ${b.start_time} - ${b.status} `;
    if (b.status === "confirmed" && !b.customer) {
      const btn = document.createElement("button");
      btn.textContent = "Cancel";
      btn.onclick = () => cancelBooking(b.id);
      li.appendChild(btn);
    }
    list.appendChild(li);
  }
}

// cancel booking function


async function cancelBooking(id) {
  const token = localStorage.getItem("token");
  await fetch(`/bookings/${id}/cancel`, {
    method: "PATCH",
    headers: {"Authorization": "Bearer " + token},
  });
  loadBookings();
}

// register function
async function register() {
  const msg = document.getElementById("signup-msg");
  const res = await fetch("/register", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      name: document.getElementById("su-name").value,
      email: document.getElementById("su-email").value,
      password: document.getElementById("su-password").value,
      role: document.getElementById("su-role").value,
    }),
  });
  if (res.status === 201) {
    msg.textContent = "Account created. You can log in now.";
  } else if (res.status === 409) {
    msg.textContent = "That email is already registered";
  } else if (res.status === 422) {
    msg.textContent = "Check your details (password needs 8+ characters)";
  } else {
    msg.textContent = "Something went wrong";
  }
}

 // owner post helper function

async function ownerPost(url, body, msgId, okText) {
  const token = localStorage.getItem("token");
  const msg = document.getElementById(msgId);
  if (!token) {
    msg.textContent = "Please log in first";
    return;
  }
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token,
    },
    body: JSON.stringify(body),
  });
  if (res.status === 201) {
    msg.textContent = okText;
  } else if (res.status === 401 || res.status === 403) {
    msg.textContent = "Log in as a business owner";
  } else {
    msg.textContent = "Check your details";
  }
  return res.status === 201;
}

async function addService() {
  const ok = await ownerPost("/services", {
    name: document.getElementById("svc-name").value,
    duration_min: Number(document.getElementById("svc-duration").value),
    price: Number(document.getElementById("svc-price").value),
  }, "svc-msg", "Service added");
  if (ok) location.reload();
}

function setHours() {
  ownerPost("/availability", {
    day_of_week: document.getElementById("av-day").value,
    start_time: document.getElementById("av-start").value,
    end_time: document.getElementById("av-end").value,
  }, "av-msg", "Hours saved");
}