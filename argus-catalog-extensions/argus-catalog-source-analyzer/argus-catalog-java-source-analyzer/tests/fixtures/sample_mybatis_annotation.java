package com.example.mapper;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface OrderMapper {

    @Select("SELECT * FROM orders WHERE id = #{id}")
    Order findById(Long id);

    @Select("SELECT o.*, u.username FROM orders o JOIN users u ON o.user_id = u.id WHERE o.status = #{status}")
    List<Order> findByStatusWithUser(String status);

    @Insert("INSERT INTO orders (user_id, order_no, total, status) VALUES (#{userId}, #{orderNo}, #{total}, #{status})")
    void insert(Order order);

    @Update("UPDATE orders SET status = #{status} WHERE id = #{id}")
    void updateStatus(Long id, String status);

    @Delete("DELETE FROM orders WHERE id = #{id}")
    void deleteById(Long id);

    @Select({"SELECT o.order_no, oi.product_name, oi.quantity",
             "FROM orders o",
             "JOIN order_items oi ON o.id = oi.order_id",
             "WHERE o.id = #{orderId}"})
    List<Map<String, Object>> findOrderDetails(Long orderId);
}
