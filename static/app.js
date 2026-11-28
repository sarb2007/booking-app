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
}