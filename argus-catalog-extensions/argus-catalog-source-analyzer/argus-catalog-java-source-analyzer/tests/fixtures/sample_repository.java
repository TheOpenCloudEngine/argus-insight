package com.example.repository;

import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;
import com.example.domain.User;

public class UserRepository {

    @PersistenceContext
    private EntityManager em;

    public User findById(Long id) {
        return em.find(User.class, id);
    }

    public void save(User user) {
        em.persist(user);
    }

    public List<User> findActiveUsers() {
        return em.createQuery("SELECT u FROM User u WHERE u.active = true").getResultList();
    }

    public List<Object[]> findUserStats() {
        return em.createNativeQuery("SELECT u.username, COUNT(o.id) FROM users u LEFT JOIN orders o ON u.id = o.user_id GROUP BY u.username").getResultList();
    }

    public void deactivateUser(Long userId) {
        em.createNativeQuery("UPDATE users SET active = false WHERE id = :id").setParameter("id", userId).executeUpdate();
    }
}
