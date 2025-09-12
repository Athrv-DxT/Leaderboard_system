// Import Firebase
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import {
  getFirestore,
  collection,
  addDoc,
  getDocs,
  onSnapshot,
  query,
  orderBy
} from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

// ✅ Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyD_9El1Ivnv_t-VafCuOHQTeAehPL0KQ3c",
  authDomain: "funfinity-c3cb4.firebaseapp.com",
  projectId: "funfinity-c3cb4",
  storageBucket: "funfinity-c3cb4.firebasestorage.app",
  messagingSenderId: "623442330452",
  appId: "1:623442330452:web:3d6a683d573cd7ce947ec1"
};

// ✅ Initialize Firebase
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

// 🔹 Test Firestore connection
async function testFirestore() {
  try {
    // Add a test entry
    await addDoc(collection(db, "leaderboard"), {
      name: "TestUser",
      score: 99
    });

    // Fetch all docs
    const querySnapshot = await getDocs(collection(db, "leaderboard"));
    querySnapshot.forEach((doc) => {
      console.log(doc.id, " => ", doc.data());
    });

    alert("Firestore is working ✅");
  } catch (e) {
    console.error("Error in Firestore test: ", e);
  }
}
testFirestore();

// 🔹 Real-time Leaderboard
const playersRef = collection(db, "players");
const q = query(playersRef, orderBy("score", "desc"));

onSnapshot(q, (snapshot) => {
  const players = [];
  snapshot.forEach((doc) => {
    players.push(doc.data());
  });
  renderLeaderboard(players);
});

// 🔹 Render leaderboard in DOM
function renderLeaderboard(players) {
  // Top 3
  document.getElementById("p1-name").textContent = players[0]?.name || "—";
  document.getElementById("p1-score").textContent = players[0]?.score || "0";

  document.getElementById("p2-name").textContent = players[1]?.name || "—";
  document.getElementById("p2-score").textContent = players[1]?.score || "0";

  document.getElementById("p3-name").textContent = players[2]?.name || "—";
  document.getElementById("p3-score").textContent = players[2]?.score || "0";

  // Others
  const tbody = document.getElementById("leaderboard-body");
  tbody.innerHTML = "";

  players.slice(3).forEach((player, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${index + 4}</td>
      <td>${player.name}</td>
      <td>${player.score}</td>
    `;
    tbody.appendChild(row);
  });
}
